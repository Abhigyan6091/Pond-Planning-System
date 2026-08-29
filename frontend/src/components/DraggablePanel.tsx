import React, { useState, useRef, useEffect } from 'react';
import { Minus, Plus, X, GripHorizontal, ChevronDown, ChevronUp } from 'lucide-react';

interface DraggablePanelProps {
  id?: string;
  title: React.ReactNode;
  subtitle?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  initialPosition?: { top?: number | string; right?: number | string; bottom?: number | string; left?: number | string };
  defaultCollapsed?: boolean;
  onClose?: () => void;
  width?: string;
  maxHeight?: string;
  headerBadge?: React.ReactNode;
  headerActions?: React.ReactNode;
  zIndex?: number;
  className?: string;
}

export const DraggablePanel: React.FC<DraggablePanelProps> = ({
  id,
  title,
  subtitle,
  icon,
  children,
  initialPosition = { top: 80, right: 16 },
  defaultCollapsed = false,
  onClose,
  width = '320px',
  maxHeight = 'calc(100vh - 120px)',
  headerBadge,
  headerActions,
  zIndex = 920,
  className = '',
}) => {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ startX: number; startY: number; initialX: number; initialY: number }>({
    startX: 0,
    startY: 0,
    initialX: 0,
    initialY: 0,
  });
  const panelRef = useRef<HTMLDivElement>(null);

  // Drag handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button, input, select, a, textarea')) {
      return; // don't drag if clicking a button or control
    }
    e.preventDefault();
    const rect = panelRef.current?.getBoundingClientRect();
    if (!rect) return;

    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: position ? position.x : rect.left,
      initialY: position ? position.y : rect.top,
    };
    setIsDragging(true);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const dx = e.clientX - dragStartRef.current.startX;
      const dy = e.clientY - dragStartRef.current.startY;
      const newX = Math.max(10, Math.min(window.innerWidth - 100, dragStartRef.current.initialX + dx));
      const newY = Math.max(10, Math.min(window.innerHeight - 50, dragStartRef.current.initialY + dy));
      setPosition({ x: newX, y: newY });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const style: React.CSSProperties = {
    zIndex,
    width,
    maxHeight,
    position: 'absolute',
    ...(position
      ? { left: `${position.x}px`, top: `${position.y}px`, right: 'auto', bottom: 'auto' }
      : {
          top: initialPosition.top,
          right: initialPosition.right,
          bottom: initialPosition.bottom,
          left: initialPosition.left,
        }),
  };

  return (
    <div
      ref={panelRef}
      id={id}
      style={style}
      className={`bg-[#0d121c]/95 backdrop-blur-md border border-[#1f293d] rounded-xl shadow-2xl overflow-hidden flex flex-col transition-all duration-75 ${
        isDragging ? 'opacity-90 ring-2 ring-cyan-500/50 shadow-cyan-950/50' : ''
      } ${className}`}
    >
      {/* Draggable Header */}
      <div
        onMouseDown={handleMouseDown}
        className="flex items-center justify-between px-3 py-2.5 bg-[#121824] border-b border-[#1f293d] select-none cursor-move group hover:bg-[#161f30] transition-colors"
      >
        <div className="flex items-center space-x-2 min-w-0 pr-2">
          <GripHorizontal className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 shrink-0" />
          {icon && <span className="shrink-0">{icon}</span>}
          <div className="min-w-0">
            <div className="flex items-center space-x-1.5">
              <span className="text-xs font-bold text-slate-200 truncate">{title}</span>
              {headerBadge}
            </div>
            {subtitle && !isCollapsed && (
              <p className="text-[10px] font-mono text-slate-400 truncate leading-tight">{subtitle}</p>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-1 shrink-0">
          {headerActions}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 text-slate-400 hover:text-cyan-400 hover:bg-slate-800/60 rounded transition-colors"
            title={isCollapsed ? 'Expand panel' : 'Minimize panel'}
          >
            {isCollapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded transition-colors"
              title="Close panel"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      {!isCollapsed && (
        <div className="p-3 overflow-y-auto overflow-x-hidden space-y-3 custom-scrollbar">
          {children}
        </div>
      )}
    </div>
  );
};
