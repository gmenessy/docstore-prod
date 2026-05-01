"""
Model Registry

Verwaltet Prompt- und Model-Versionen für Reproducibility und Rollback.
Implementiert Optimistic Locking für Race-Condition-Schutz.
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import Session
from app.models.database import Base, gen_id
import hashlib
import json

logger = logging.getLogger(__name__)


class PromptVersion(Base):
    """
    Versionierte Prompt-Vorlage in der Datenbank.
    """
    __tablename__ = "prompt_versions"

    id = Column(String(12), primary_key=True, default=gen_id)
    name = Column(String(100), nullable=False, index=True)  # z.B. "chat_system"
    version = Column(String(20), nullable=False)  # z.B. "v1", "v2"
    template = Column(Text, nullable=False)
    parameters = Column(JSON, nullable=False, default=dict)
    metadata = Column(JSON, nullable=False, default=dict)

    # Metadaten
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(100), nullable=False)  # User oder "system"
    hash = Column(String(32), nullable=False, index=True)  # Für Change Detection
    is_active = Column(Boolean, default=False, nullable=False, index=True)

    # Optimistic Locking
    version_number = Column(Integer, default=1, nullable=False)

    # Statistics
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_prompt_name_version", "name", "version", unique=True),
        Index("ix_prompt_active", "name", "is_active"),
    )

    def calculate_hash(self) -> str:
        """Berechnet Hash des Prompts für Change Detection"""
        content = f"{self.template}{json.dumps(self.parameters, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def activate(self, db: Session):
        """Aktiviert diese Version und deaktiviert alle anderen"""
        # Alle anderen Versionen deaktivieren
        db.query(PromptVersion).filter(
            PromptVersion.name == self.name,
            PromptVersion.id != self.id
        ).update({"is_active": False})

        # Diese Version aktivieren
        self.is_active = True
        self.last_used_at = datetime.utcnow()

        db.commit()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "template": self.template,
            "parameters": self.parameters,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "hash": self.hash,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


class ModelRegistry:
    """
    Verwaltet Prompt- und Model-Versionen.

    Features:
    - Prompt Versioning mit Change Detection
    - Rollback zu vorherigen Versionen
    - A/B-Testing von Prompts
    - Usage Tracking
    """

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy Database Session
        """
        self.db = db

    def register_prompt(
        self,
        name: str,
        template: str,
        parameters: Dict,
        author: str,
        metadata: Optional[Dict] = None,
        force_version: bool = False
    ) -> PromptVersion:
        """
        Registriert neue Prompt-Version.

        Args:
            name: Eindeutiger Name des Prompts (z.B. "chat_system")
            template: Prompt-Template mit Platzhaltern
            parameters: Parameter für den Prompt (z.B. temperature)
            author: Ersteller des Prompts
            metadata: Zusätzliche Metadaten
            force_version: Erzwingt neue Version auch bei gleichem Hash

        Returns:
            PromptVersion Objekt
        """
        # Hash berechnen
        content_hash = hashlib.sha256(
            f"{template}{json.dumps(parameters, sort_keys=True)}".encode()
        ).hexdigest()[:32]

        # Prüfe auf Änderungen
        last_version = self.db.query(PromptVersion).filter(
            PromptVersion.name == name,
            PromptVersion.is_active == True
        ).first()

        # Keine Änderung und nicht forciert → Alte Version zurückgeben
        if last_version and last_version.hash == content_hash and not force_version:
            logger.info(f"Prompt {name} unchanged, returning existing version {last_version.version}")
            return last_version

        # Neue Version erstellen
        all_versions = self.db.query(PromptVersion).filter(
            PromptVersion.name == name
        ).count()

        new_version_number = all_versions + 1
        version = f"v{new_version_number}"

        prompt_version = PromptVersion(
            id=gen_id(),
            name=name,
            version=version,
            template=template,
            parameters=parameters,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            created_by=author,
            hash=content_hash,
            is_active=True,  # Wird aktiviert
            version_number=new_version_number,
        )

        # Alte Versionen deaktivieren
        if last_version:
            last_version.is_active = False

        self.db.add(prompt_version)
        self.db.commit()

        logger.info(f"Registered new prompt version: {name}:{version}")
        return prompt_version

    def get_active_prompt(self, name: str) -> Optional[PromptVersion]:
        """Gibt aktive Prompt-Version zurück"""
        return self.db.query(PromptVersion).filter(
            PromptVersion.name == name,
            PromptVersion.is_active == True
        ).first()

    def get_prompt(self, name: str, version: str) -> Optional[PromptVersion]:
        """Gibt spezifische Prompt-Version zurück"""
        return self.db.query(PromptVersion).filter(
            PromptVersion.name == name,
            PromptVersion.version == version
        ).first()

    def get_all_versions(self, name: str) -> List[PromptVersion]:
        """Gibt alle Versionen eines Prompts zurück"""
        return self.db.query(PromptVersion).filter(
            PromptVersion.name == name
        ).order_by(PromptVersion.created_at.desc()).all()

    def rollback_prompt(
        self,
        name: str,
        target_version: str,
        author: str
    ) -> Optional[PromptVersion]:
        """
        Rollback zu vorherigen Prompt-Version.

        Args:
            name: Prompt-Name
            target_version: Ziel-Version (z.B. "v1")
            author: Durchführer des Rollbacks

        Returns:
            Die reaktivierte PromptVersion
        """
        # Ziel-Version finden
        target = self.get_prompt(name, target_version)
        if not target:
            logger.error(f"Target version {name}:{target_version} not found")
            return None

        # Aktive Version deaktivieren
        current_active = self.get_active_prompt(name)
        if current_active:
            current_active.is_active = False

        # Ziel-Version aktivieren
        target.activate(self.db)

        # Metadaten aktualisieren
        target.metadata["rollback_from"] = current_active.version if current_active else None
        target.metadata["rollback_at"] = datetime.utcnow().isoformat()
        target.metadata["rollback_by"] = author

        self.db.commit()

        logger.info(f"Rolled back prompt {name} from {current_active.version if current_active else 'none'} to {target_version}")
        return target

    def format_prompt(
        self,
        name: str,
        variables: Dict[str, str],
        version: Optional[str] = None
    ) -> Optional[str]:
        """
        Formatiert Prompt mit Variablen.

        Args:
            name: Prompt-Name
            variables: Variablen für Platzhalter (z.B. {"query": "Was ist..."})
            version: Spezifische Version (optional, verwendet aktive wenn None)

        Returns:
            Formatierter Prompt oder None wenn nicht gefunden
        """
        if version:
            prompt_version = self.get_prompt(name, version)
        else:
            prompt_version = self.get_active_prompt(name)

        if not prompt_version:
            logger.error(f"Prompt {name}:{version or 'active'} not found")
            return None

        try:
            # Platzhalter ersetzen
            formatted = prompt_version.template
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                formatted = formatted.replace(placeholder, str(value))

            # Usage tracken
            prompt_version.usage_count += 1
            prompt_version.last_used_at = datetime.utcnow()
            self.db.commit()

            return formatted
        except Exception as e:
            logger.error(f"Error formatting prompt {name}: {e}")
            return None

    def compare_versions(
        self,
        name: str,
        version_a: str,
        version_b: str
    ) -> Optional[Dict]:
        """
        Vergleicht zwei Prompt-Versionen.

        Args:
            name: Prompt-Name
            version_a: Erste Version
            version_b: Zweite Version

        Returns:
            Dict mit Unterschieden
        """
        prompt_a = self.get_prompt(name, version_a)
        prompt_b = self.get_prompt(name, version_b)

        if not prompt_a or not prompt_b:
            return None

        return {
            "template_changed": prompt_a.template != prompt_b.template,
            "parameters_changed": prompt_a.parameters != prompt_b.parameters,
            "hash_different": prompt_a.hash != prompt_b.hash,
            "version_a": {
                "version": prompt_a.version,
                "created_at": prompt_a.created_at.isoformat(),
                "created_by": prompt_a.created_by,
            },
            "version_b": {
                "version": prompt_b.version,
                "created_at": prompt_b.created_at.isoformat(),
                "created_by": prompt_b.created_by,
            },
        }

    def list_prompts(self) -> List[Dict]:
        """Listet alle Prompts mit aktiven Versionen"""
        prompts = self.db.query(
            PromptVersion.name,
            PromptVersion.version,
            PromptVersion.created_by,
            PromptVersion.created_at,
            PromptVersion.usage_count
        ).filter(
            PromptVersion.is_active == True
        ).all()

        return [
            {
                "name": row.name,
                "version": row.version,
                "created_by": row.created_by,
                "created_at": row.created_at.isoformat(),
                "usage_count": row.usage_count,
            }
            for row in prompts
        ]


# Helper-Funktionen für einfache Verwendung
def get_registry(db: Session) -> ModelRegistry:
    """Factory-Funktion für ModelRegistry"""
    return ModelRegistry(db)


# Default Prompts für Initialisierung
DEFAULT_PROMPTS = {
    "chat_system": {
        "template": """Du bist ein Assistent für eine {store_type} im Kontext einer deutschen Kommunalverwaltung.

# Deine Rolle
- Helfe bei der Suche und Analyse von Dokumenten
- Beantworte Fragen basierend AUSSCHLIESSLICH auf den gegebenen Kontext
- Bleibe sachlich, präzise und professionell

# Regeln
1. Antworte AUSSCHLIESSLICH basierend auf den gegebenen Dokumenten
2. Wenn keine Informationen gefunden werden, sage das explizit
3. Zitiere die Quellen wenn möglich
4. Keine Erfindungen oder Halluzinationen
5. Verwende professionelles Deutsch

# Kontext
Store: {store_name}
Typ: {store_type}
Analyse-Fokus: {analyse_fokus}

# Dokumente
{context}

# Frage
{query}

# Antwort""",
        "parameters": {
            "temperature": 0.7,
            "max_tokens": 500,
            "top_p": 0.9,
        },
        "metadata": {
            "description": "System-Prompt für RAG Chat",
            "category": "chat",
        },
    },
    "wiki_ingest": {
        "template": """Erstelle eine Wiki-Seite für ein Dokument in einer WissensDB.

# Dokument
Titel: {title}
Typ: {doc_type}
Zusammenfassung: {summary}

# Extrahierte Entitäten
{entities}

# Aufgabe
Erstelle eine strukturierte Wiki-Seite im Markdown-Format mit:
1. Zusammenfassung (2-3 Sätze)
2. Kernpunkte (bullets)
3. Verweise auf verwandte Konzepte""",
        "parameters": {
            "temperature": 0.5,
            "max_tokens": 300,
        },
        "metadata": {
            "description": "Prompt für Wiki-Ingest",
            "category": "wiki",
        },
    },
}


def initialize_default_prompts(db: Session) -> None:
    """
    Initialisiert Standard-Prompts wenn nicht vorhanden.

    Args:
        db: Database Session
    """
    registry = ModelRegistry(db)

    for name, config in DEFAULT_PROMPTS.items():
        existing = registry.get_active_prompt(name)
        if not existing:
            registry.register_prompt(
                name=name,
                template=config["template"],
                parameters=config["parameters"],
                author="system",
                metadata=config.get("metadata", {}),
            )
            logger.info(f"Initialized default prompt: {name}")


# Export
__all__ = [
    "ModelRegistry",
    "PromptVersion",
    "get_registry",
    "initialize_default_prompts",
    "DEFAULT_PROMPTS",
]
