import React, { useState, useRef, useEffect } from 'react';
import { GripHorizontal, Minus, Plus, X } from 'lucide-react';

export const DraggableWidget = ({
  id,
  title,
  icon: Icon,
  initialPos = { x: 50, y: 100 },
  children,
  width = 'auto',
  className = '',
  onClose
}) => {
  const [pos, setPos] = useState(() => {
    try {
      const saved = localStorage.getItem(`jasva_pos_${id}`);
      if (saved) return JSON.parse(saved);
    } catch (_) {}
    return initialPos;
  });

  const [isDragging, setIsDragging] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const dragRef = useRef({ startX: 0, startY: 0, initialPosX: 0, initialPosY: 0 });

  const handleMouseDown = (e) => {
    // Only drag on primary mouse button
    if (e.button !== 0) return;
    setIsDragging(true);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialPosX: pos.x,
      initialPosY: pos.y
    };
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;

      const newX = Math.max(10, Math.min(window.innerWidth - 80, dragRef.current.initialPosX + dx));
      const newY = Math.max(10, Math.min(window.innerHeight - 60, dragRef.current.initialPosY + dy));

      setPos({ x: newX, y: newY });
    };

    const handleMouseUp = () => {
      if (isDragging) {
        setIsDragging(false);
        try {
          localStorage.setItem(`jasva_pos_${id}`, JSON.stringify(pos));
        } catch (_) {}
      }
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, pos, id]);

  useEffect(() => {
    const handleResize = () => {
      setPos(prev => ({
        x: Math.max(10, Math.min(window.innerWidth - 300, prev.x)),
        y: Math.max(10, Math.min(window.innerHeight - 80, prev.y))
      }));
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div
      className={`draggable-hologram-widget ${isDragging ? 'dragging' : ''} ${className}`}
      style={{
        left: `${pos.x}px`,
        top: `${pos.y}px`,
        width: typeof width === 'number' ? `${width}px` : width
      }}
    >
      {/* ─── DRAGGABLE HEADER HANDLE (ONLY DRAGGABLE HERE) ─── */}
      <div
        className="widget-drag-header"
        onMouseDown={handleMouseDown}
        title="Drag by heading"
      >
        <div className="widget-drag-title">
          {Icon && <Icon size={12} className="widget-header-icon" />}
          <span className="widget-title-text">{title}</span>
          <GripHorizontal size={11} className="widget-grip-dots" />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            className="widget-collapse-btn"
            onClick={(e) => {
              e.stopPropagation();
              setIsCollapsed(!isCollapsed);
            }}
            title={isCollapsed ? 'Expand' : 'Collapse'}
          >
            {isCollapsed ? <Plus size={10} /> : <Minus size={10} />}
          </button>
          {onClose && (
            <button
              className="widget-collapse-btn"
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              title="Close Panel"
            >
              <X size={11} />
            </button>
          )}
        </div>
      </div>

      {/* ─── WIDGET BODY ─── */}
      {!isCollapsed && <div className="widget-drag-body">{children}</div>}
    </div>
  );
};
