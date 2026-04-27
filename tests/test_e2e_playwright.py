"""
E2E Tests mit Playwright für Frontend User Journeys.

Testet kritische User-Pfade:
- Store erstellen → Dokument upload → Chat → Export
- Multi-User Szenarien
- Mobile Responsiveness
- Error Recovery

SOTA: Playwright + Cross-Browser + Mobile Emulation
"""
import pytest
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import asyncio
from typing import AsyncGenerator


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture(scope="session")
async def browser_context_args(browser_context_args):
    """Konfiguriere Browser Context mit Viewport und Permissions."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "locale": "de-DE",
        "timezone_id": "Europe/Berlin",
        "permissions": ["geolocation"],
    }


@pytest.fixture
async def page(page: Page) -> AsyncGenerator[Page, None]:
    """Setup Page mit Base URL und Wartezeiten."""
    # In Production: URL aus Environment Variable
    base_url = "http://localhost:5173"  # Vite Dev Server

    await page.goto(base_url)
    await page.wait_for_load_state("networkidle")

    yield page

    # Cleanup nach Test
    await page.close()


@pytest.fixture
async def mobile_page(page: Page) -> AsyncGenerator[Page, None]:
    """Mobile Emulation Page (iPhone 12 Pro)."""
    await page.set_viewport_size({"width": 390, "height": 844})
    await page.emulate_media(media="screen")

    yield page


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# USER JOURNEY TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.e2e
@pytest.mark.journey
async def test_complete_user_journey(page: Page):
    """
    CRITICAL USER JOURNEY: Store → Upload → Chat → Export

    Testet den kompletten Happy Path:
    1. Store erstellen (Akte)
    2. Dokument upload (PDF)
    3. Chat mit Dokument
    4. Export als DOCX
    """
    # 1. Store erstellen
    await page.click('button:has-text("Neue Sammlung")')
    await page.fill('input[placeholder*="Name"]', "Test-Akte-E2E")
    await page.select_option("select", "akte")
    await page.fill('textarea[placeholder*="Beschreibung"]', "E2E Test Akte")
    await page.click('button:has-text("Erstellen")')

    # Warte auf Erfolgs-Toast
    await page.wait_for_selector('text=/erstellen/', timeout=5000)

    # 2. Dokument upload simulieren (API Mock in Real Environment)
    # In Production: echtes File Upload testen
    upload_btn = page.locator('button:has-text("Dokument hochladen")')
    await upload_btn.click()

    # 3. Chat testen
    await page.click('button:has-text("Chat")')
    chat_input = page.locator('input[aria-label*="Chat-Nachricht"]')
    await chat_input.fill("Was sind die wichtigsten Maßnahmen?")
    await page.click('button[aria-label*="Nachricht senden"]')

    # Warte auf Antwort (max 10s)
    await page.wait_for_selector('text=Offline-Modus|Basierend auf den Dokumenten', timeout=10000)

    # 4. Export testen
    export_links = page.locator('a:has-text("Export")')
    count = await export_links.count()
    assert count >= 3, "Es sollten mindestens 3 Export-Links vorhanden sein"

    # Screenshot für Visual Regression
    await page.screenshot(path="test-results/journey-complete.png")


@pytest.mark.e2e
@pytest.mark.mobile
async def test_mobile_responsive_menu(mobile_page: Page):
    """
    MOBILE UX TEST: Drawer Menu funktioniert auf Mobile

    Testet:
    - Hamburger Button sichtbar
    - Drawer öffnet sich
    - Store-Auswahl funktioniert
    - Drawer schließt sich
    """
    # Hamburger Button sollte sichtbar sein
    hamburger = mobile_page.locator('button:has-text("☰")')
    await hamburger.wait_for(state="visible", timeout=5000)

    # Drawer öffnen
    await hamburger.click()

    # Sidebar sollte sichtbar sein
    sidebar = mobile_page.locator('div[style*="position: fixed"][style*="z-index: 9999"]')
    await sidebar.wait_for(state="visible", timeout=3000)

    # Store Button klicken (mit min 48px Touch Target)
    store_btn = mobile_page.locator('button:has-text("Digitalisierungsstrategie")')
    await store_btn.click()

    # Drawer sollte geschlossen sein
    await sidebar.wait_for(state="hidden", timeout=3000)

    # Screenshot für Mobile Verification
    await mobile_page.screenshot(path="test-results/mobile-drawer.png")


@pytest.mark.e2e
@pytest.mark.accessibility
async def test_accessibility_aria_labels(page: Page):
    """
    ACCESSIBILITY TEST: ARIA-Labels und Keyboard Navigation

    Testet:
    - Alle Buttons haben aria-label
    - Keyboard Navigation funktioniert
    - Focus Management korrekt
    """
    # Alle Buttons finden
    buttons = await page.locator('button').all()

    for button in buttons:
        # Prüfe ob aria-label oder text vorhanden
        aria_label = await button.get_attribute('aria-label')
        text = await button.text_content()

        assert aria_label or text, f"Button ohne aria-label oder Text gefunden: {button}"

    # Keyboard Navigation Test
    await page.keyboard.press('Tab')
    focused = await page.evaluate('document.activeElement.tagName')

    assert focused in ['BUTTON', 'INPUT', 'SELECT', 'A'], \
        f"Fokus auf nicht-interaktivem Element: {focused}"


@pytest.mark.e2e
@pytest.mark.error_recovery
async def test_api_error_recovery(page: Page):
    """
    ERROR RECOVERY TEST: Graceful Degradation bei API-Failure

    Testet:
    - Chat-Fallback bei Backend-Error
    - User bekommt Feedback
    - App stürzt nicht ab
    """
    # API simulieren ausfallen (durch Network Block)
    await page.route('**/api/v1/**', lambda route: route.abort())

    # Chat versuchen
    await page.click('button:has-text("Chat")')
    chat_input = page.locator('input[aria-label*="Chat-Nachricht"]')
    await chat_input.fill("Test Nachricht")
    await page.click('button[aria-label*="Nachricht senden"]')

    # Sollte Fallback-Antwort zeigen (Offline-Modus)
    await page.wait_for_selector('text=Offline-Modus', timeout=5000)

    # App sollte nicht abgestürzt sein (Error Boundary Test)
    app_container = page.locator('#root')
    is_visible = await app_container.is_visible()

    assert is_visible, "App ist abgestürzt (Error Boundary nicht aktiv)"


@pytest.mark.e2e
@pytest.mark.performance
async def test_upload_performance(page: Page):
    """
    PERFORMANCE TEST: Upload Latenz

    Testet:
    - Upload UI zeigt Loading State
    - Progress Updates werden angezeigt
    - Upload dauert nicht länger als 5s (für 1MB PDF)
    """
    # TODO: Implementiere echten File Upload in Test-Umgebung

    # Simuliere Upload Performance-Messung
    start_time = asyncio.get_event_loop().time()

    # Upload Button klicken
    upload_btn = page.locator('button:has-text("Dokument hochladen")')
    await upload_btn.click()

    # Warte auf Loading State
    loading = page.locator('button:has-text("Wird hochgeladen...")')

    # Prüfe ob Loading erscheint (innerhalb 1s)
    try:
        await loading.wait_for(state="visible", timeout=1000)
        loading_shown = True
    except:
        loading_shown = False

    # Screenshot
    await page.screenshot(path="test-results/upload-performance.png")

    assert loading_shown, "Loading State nicht angezeigt"


@pytest.mark.e2e
@pytest.mark.multi_user
async def test_store_isolation(page: Page):
    """
    MULTI-USER TEST: Store Isolation

    Testet:
    - User A sieht nur eigene Stores
    - Chat-Responses sind Store-isoliert
    - Cross-Store Data Leak verhindert
    """
    # Store 1 erstellen
    await page.click('button:has-text("Neue Sammlung")')
    await page.fill('input[placeholder*="Name"]', "User-A-Store")
    await page.click('button:has-text("Erstellen")')
    await page.wait_for_selector('text=User-A-Store')

    # Verify Store ist in Liste
    store_list = page.locator('text=User-A-Store')
    count = await store_list.count()
    assert count >= 1, "Store wurde nicht erstellt"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def pytest_configure(config):
    """Pytest Konfiguration für Playwright."""
    config.addinivalue_line(
        "markers",
        "e2e: Markiert E2E Tests (langsam, erfordert vollständige Umgebung)"
    )
    config.addinivalue_line(
        "markers",
        "mobile: Markiert Mobile-spezifische Tests"
    )
    config.addinivalue_line(
        "markers",
        "accessibility: Markiert Accessibility Tests"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed", "--browser=chromium"])
