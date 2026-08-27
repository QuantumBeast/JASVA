import React, { useState, useRef, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';
import {
  Send,
  Image as ImageIcon,
  X,
  Copy,
  Check,
  ChevronDown,
  Brain,
  Globe,
  Terminal,
  Calendar,
  Sparkles,
  Smartphone,
  Tv
} from 'lucide-react';

export const ChatPanel = () => {
  const {
    messages,
    attachedImage,
    setAttachedImage,
    sphereState,
    sendCommand,
    togglePanel
  } = useJasva();

  const [inputVal, setInputVal] = useState('');
  const [copiedId, setCopiedId] = useState(null);
  const [expandedThoughts, setExpandedThoughts] = useState({});
  const chatContainerRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, sphereState.isProcessing]);

  const handleSend = () => {
    if (!inputVal.trim() && !attachedImage) return;
    sendCommand(inputVal);
    setInputVal('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickChip = (prompt) => {
    setInputVal(prompt);
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      setAttachedImage({ name: file.name, src: event.target.result });
    };
    reader.readAsDataURL(file);
  };

  const copyCode = (codeText, id) => {
    navigator.clipboard.writeText(codeText);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleThought = (id) => {
    setExpandedThoughts(prev => ({ ...prev, [id]: !prev[id] }));
  };

  // Helper to render message content with inline code and fenced code blocks
  const renderMessageContent = (text) => {
    if (!text) return null;

    // Check for code blocks ```lang ... ```
    const parts = text.split(/(```[\s\S]*?```)/g);

    return parts.map((part, index) => {
      if (part.startsWith('```') && part.endsWith('```')) {
        const lines = part.slice(3, -3).trim().split('\n');
        const lang = lines[0].match(/^[a-zA-Z0-9_-]+$/) ? lines[0] : 'CODE';
        const codeContent = lang !== 'CODE' ? lines.slice(1).join('\n') : lines.join('\n');
        const blockId = `code-${index}`;

        return (
          <div key={index} className="code-block-wrapper">
            <div className="code-block-header">
              <span>{lang.toUpperCase()}</span>
              <button
                className="copy-code-btn"
                onClick={() => copyCode(codeContent, blockId)}
                title="Copy code"
              >
                {copiedId === blockId ? <Check size={11} color="#00ff87" /> : <Copy size={11} />}
                <span>{copiedId === blockId ? 'COPIED' : 'COPY'}</span>
              </button>
            </div>
            <pre style={{ padding: '10px 12px', fontSize: '11.5px', color: 'var(--accent-color)', overflowX: 'auto' }}>
              <code>{codeContent}</code>
            </pre>
          </div>
        );
      }

      // Normal text with line breaks
      return (
        <div key={index} style={{ whiteSpace: 'pre-wrap' }}>
          {part}
        </div>
      );
    });
  };

  const statusClass = sphereState.isListening
    ? 'status-dot listening'
    : sphereState.isProcessing
    ? 'status-dot processing'
    : 'status-dot';

  const statusLabel = sphereState.isListening
    ? 'JARVIS LISTENING'
    : sphereState.isProcessing
    ? 'JARVIS PROCESSING'
    : 'JARVIS STANDBY';

  return (
    <div className="panel-window left-panel chat-panel" id="chatPanel">
      {/* Panel Header */}
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-title">NEURAL CHAT</span>
          <div className="system-status">
            <span className={statusClass}></span>
            <span className="status-text">{statusLabel}</span>
          </div>
        </div>
        <button
          className="panel-close-dot"
          onClick={() => togglePanel('chatPanel')}
          title="Close Panel"
        ></button>
      </div>

      {/* Message Feed */}
      <div className="chat-container" ref={chatContainerRef}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat-message ${msg.sender === 'user' ? 'user-message' : 'bot-message'}`}
          >
            <div className="message-sender">
              <span className="sender-avatar">{msg.sender === 'user' ? 'ME' : 'AI'}</span>
              <span>{msg.name}</span>
            </div>

            {/* Attached Image Preview */}
            {msg.image && (
              <img
                src={msg.image}
                alt="Attachment"
                style={{ maxHeight: '140px', borderRadius: '8px', marginBottom: '8px' }}
              />
            )}

            {/* Thought Accordion */}
            {msg.thought && (
              <div className="thought-container">
                <div
                  className="thought-header"
                  onClick={() => toggleThought(msg.id)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Brain size={13} color="var(--accent-color)" />
                    <span>Thought Process</span>
                  </div>
                  <ChevronDown
                    size={12}
                    style={{
                      transform: expandedThoughts[msg.id] ? 'rotate(180deg)' : 'none',
                      transition: 'transform 0.2s ease'
                    }}
                  />
                </div>
                {expandedThoughts[msg.id] && (
                  <div className="thought-body">
                    {msg.thought}
                  </div>
                )}
              </div>
            )}

            {/* Message Text */}
            <div className="message-text">
              {renderMessageContent(msg.text)}
            </div>
          </div>
        ))}

        {/* Processing Indicator */}
        {sphereState.isProcessing && (
          <div className="chat-message bot-message" style={{ opacity: 0.85 }}>
            <div className="message-sender">
              <span className="sender-avatar">AI</span>
              <span>JARVIS</span>
            </div>
            <div style={{ fontStyle: 'italic', color: 'var(--accent-color)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sparkles size={13} className="spinning" />
              <span>Analyzing & executing action...</span>
            </div>
          </div>
        )}
      </div>

      {/* Quick Action Chips for Instant 1-Click Zero-Learning Usage */}
      <div className="quick-action-chips-dock">
        <button
          className="quick-chip"
          onClick={() => handleQuickChip('search for ')}
          title="Search the web"
        >
          <Globe size={10} />
          <span>Web Search</span>
        </button>
        <button
          className="quick-chip"
          onClick={() => handleQuickChip('note: ')}
          title="Add a quick note"
        >
          <Calendar size={10} />
          <span>Add Note</span>
        </button>
        <button
          className="quick-chip"
          onClick={() => handleQuickChip('run python print("Hello")')}
          title="Run Python snippet"
        >
          <Terminal size={10} />
          <span>Run Code</span>
        </button>
        <button
          className="quick-chip"
          onClick={() => handleQuickChip('remember that ')}
          title="Teach Jarvis a memory fact"
        >
          <Brain size={10} />
          <span>Remember</span>
        </button>
      </div>

      {/* Input Dock & Attachment Previews */}
      <div className="chat-input-area">
        {attachedImage && (
          <div className="image-preview-dock">
            <img src={attachedImage.src} alt="Preview" />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {attachedImage.name}
            </span>
            <button
              onClick={() => setAttachedImage(null)}
              style={{ background: 'none', border: 'none', color: 'var(--error-color)', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        <div className="input-container">
          <input
            type="file"
            ref={fileInputRef}
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleImageUpload}
          />
          <button
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
            title="Attach Image"
          >
            <ImageIcon size={15} />
          </button>
          <textarea
            placeholder="Talk to Jarvis or execute any skill..."
            rows={1}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button onClick={handleSend} title="Send (Enter)">
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};
