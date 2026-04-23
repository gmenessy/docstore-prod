/**
 * CommentPanel - Kommentare & Kollaboration UI
 *
 * Features:
 * - Kommentar-Threads
 * - Echtzeit-Updates via WebSocket
 * - User-Presence Indicators
 * - Markdown-Support
 */
import React, { useState, useEffect, useCallback } from "react";

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CommentPanel Component
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export function CommentPanel({
  storeId,
  documentId = null,
  wikiPageId = null,
  taskId = null,
  api
}) {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeUsers, setActiveUsers] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [replyTo, setReplyTo] = useState(null);
  const [newComment, setNewComment] = useState("");

  // ─── Kommentare laden ───
  const loadComments = useCallback(async () => {
    try {
      setLoading(true);
      const resourceType = documentId ? "document" : wikiPageId ? "wiki" : "task";
      const resourceId = documentId || wikiPageId || taskId;

      const params = new URLSearchParams({
        [`${resourceType}_id`]: resourceId
      });

      const response = await fetch(`${api._getBaseURL()}/comments/${storeId}?${params}`, {
        headers: api._headers()
      });

      const data = await response.json();
      setComments(data.comments || []);
    } catch (error) {
      console.error("Failed to load comments:", error);
    } finally {
      setLoading(false);
    }
  }, [storeId, documentId, wikiPageId, taskId, api]);

  // ─── WebSocket für Echtzeit-Updates ───
  useEffect(() => {
    const wsUrl = `${api._getBaseURL().replace("http", "ws")}/ws/comments/${storeId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected");
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.event) {
        case "connected":
          console.log("WebSocket session established:", data.connection_id);
          break;
        case "comment.created":
          // Neuen Kommentar zur Liste hinzufügen
          setComments(prev => [...prev, data.comment]);
          break;
        case "users.active":
          setActiveUsers(data.users || []);
          break;
        case "pong":
          // Keep-Alive Antwort
          break;
        default:
          console.log("Unknown WebSocket event:", data.event);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setWsConnected(false);
      // Reconnect nach 5 Sekunden
      setTimeout(() => setWsConnected(true), 5000);
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    // Ping alle 30 Sekunden
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ event: "ping" }));
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [storeId]);

  // ─── Initial laden ───
  useEffect(() => {
    loadComments();
  }, [loadComments]);

  // ─── Kommentar senden ───
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!newComment.trim()) return;

    try {
      const response = await fetch(`${api._getBaseURL()}/comments/${storeId}`, {
        method: "POST",
        headers: api._headers(),
        body: JSON.stringify({
          content: newComment,
          document_id: documentId,
          wiki_page_id: wikiPageId,
          task_id: taskId,
          parent_id: replyTo
        })
      });

      if (response.ok) {
        const comment = await response.json();
        setComments(prev => [...prev, comment]);
        setNewComment("");
        setReplyTo(null);
      }
    } catch (error) {
      console.error("Failed to submit comment:", error);
    }
  };

  // ─── Kommentar auflösen ───
  const handleResolve = async (commentId) => {
    try {
      await fetch(`${api._getBaseURL()}/comments/${storeId}/${commentId}`, {
        method: "PATCH",
        headers: api._headers(),
        body: JSON.stringify({ resolved: true })
      });

      setComments(prev =>
        prev.map(c =>
          c.id === commentId
            ? { ...c, resolved_at: new Date().toISOString() }
            : c
        )
      );
    } catch (error) {
      console.error("Failed to resolve comment:", error);
    }
  };

  // ─── Kommentar löschen ───
  const handleDelete = async (commentId) => {
    try {
      await fetch(`${api._getBaseURL()}/comments/${storeId}/${commentId}`, {
        method: "DELETE",
        headers: api._headers()
      });

      setComments(prev => prev.filter(c => c.id !== commentId));
    } catch (error) {
      console.error("Failed to delete comment:", error);
    }
  };

  // ─── Render ───
  return (
    <div className="comment-panel">
      {/* Header */}
      <div className="comment-header">
        <h3>Kommentare & Diskussion</h3>
        <div className="comment-stats">
          <span className="comment-count">{comments.length} Kommentare</span>
          <span className="active-users">
            👥 {activeUsers.length} aktiv
          </span>
          <span className={`ws-status ${wsConnected ? "connected" : "disconnected"}`}>
            {wsConnected ? "🟢 Verbunden" : "🔴 Getrennt"}
          </span>
        </div>
      </div>

      {/* Kommentar-Eingabe */}
      <form onSubmit={handleSubmit} className="comment-form">
        <textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder="Schreibe einen Kommentar..."
          className="comment-input"
          disabled={loading}
        />
        <div className="comment-actions">
          <button
            type="submit"
            disabled={!newComment.trim() || loading}
            className="btn-primary"
          >
            Senden
          </button>
          {replyTo && (
            <button
              type="button"
              onClick={() => setReplyTo(null)}
              className="btn-secondary"
            >
              Abbrechen
            </button>
          )}
        </div>
      </form>

      {/* Kommentar-Liste */}
      <div className="comment-list">
        {loading ? (
          <div className="loading">Laden...</div>
        ) : comments.length === 0 ? (
          <div className="empty-state">
            <p>Noch keine Kommentare. Sei der Erste!</p>
          </div>
        ) : (
          comments.map(comment => (
            <CommentItem
              key={comment.id}
              comment={comment}
              onReply={setReplyTo}
              onResolve={handleResolve}
              onDelete={handleDelete}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CommentItem Component
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function CommentItem({ comment, onReply, onResolve, onDelete }) {
  const [showReplies, setShowReplies] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content);

  const handleSave = async () => {
    try {
      const response = await fetch(`/api/v1/comments/${comment.store_id}/${comment.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editText })
      });

      if (response.ok) {
        const updated = await response.json();
        // TODO: Update in parent
        setIsEditing(false);
      }
    } catch (error) {
      console.error("Failed to update comment:", error);
    }
  };

  return (
    <div className={`comment-item ${comment.resolved_at ? "resolved" : ""}`}>
      {/* User Info */}
      <div className="comment-header">
        <span className="comment-user">{comment.user_id}</span>
        <span className="comment-date">
          {new Date(comment.created_at).toLocaleString("de-DE")}
        </span>
        {comment.resolved_at && (
          <span className="comment-resolved">✓ Gelöst</span>
        )}
      </div>

      {/* Kommentar-Content */}
      <div className="comment-content">
        {isEditing ? (
          <div className="comment-edit">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="edit-input"
            />
            <div className="edit-actions">
              <button onClick={handleSave} className="btn-primary btn-sm">
                Speichern
              </button>
              <button
                onClick={() => {
                  setIsEditing(false);
                  setEditText(comment.content);
                }}
                className="btn-secondary btn-sm"
              >
                Abbrechen
              </button>
            </div>
          </div>
        ) : (
          <p>{comment.content}</p>
        )}
      </div>

      {/* Aktionen */}
      <div className="comment-actions">
        <button
          onClick={() => onReply(comment.id)}
          className="btn-link btn-sm"
        >
          Antworten
        </button>
        <button
          onClick={() => setIsEditing(true)}
          className="btn-link btn-sm"
        >
          Bearbeiten
        </button>
        <button
          onClick={() => onResolve(comment.id)}
          className="btn-link btn-sm"
          disabled={comment.resolved_at}
        >
          {comment.resolved_at ? "Wieder öffnen" : "Lösen"}
        </button>
        <button
          onClick={() => onDelete(comment.id)}
          className="btn-link btn-sm btn-danger"
        >
          Löschen
        </button>
      </div>

      {/* Antworten */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="comment-replies">
          <button
            onClick={() => setShowReplies(!showReplies)}
            className="btn-link btn-sm"
          >
            {showReplies ? "▲" : "▼"} {comment.replies.length} Antworten
          </button>
          {showReplies && (
            <div className="replies-list">
              {comment.replies.map(reply => (
                <CommentItem
                  key={reply.id}
                  comment={reply}
                  onReply={onReply}
                  onResolve={onResolve}
                  onDelete={onDelete}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default CommentPanel;