import React, { useState, useEffect } from 'react';
import { callBackend } from '../utils/pywebviewBridge';
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Plus,
  Trash2,
  CheckCircle2,
  Circle,
  Download,
  ExternalLink,
  Clock,
  Tag
} from 'lucide-react';

const CATEGORIES = ['WORK', 'MEET', 'TASK', 'ALERT', 'HEALTH'];

export const CalendarTab = () => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDateStr, setSelectedDateStr] = useState(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [events, setEvents] = useState([]);
  const [isAdding, setIsAdding] = useState(false);
  const [newEventTitle, setNewEventTitle] = useState('');
  const [newEventTime, setNewEventTime] = useState('09:00');
  const [newEventCategory, setNewEventCategory] = useState('WORK');
  const [exportNotice, setExportNotice] = useState('');

  // Fetch events for current month
  const fetchMonthEvents = async () => {
    try {
      const year = currentDate.getFullYear();
      const month = String(currentDate.getMonth() + 1).padStart(2, '0');
      const monthStr = `${year}-${month}`;
      const res = await callBackend('get_calendar_events', monthStr);
      if (Array.isArray(res)) {
        setEvents(res);
      }
    } catch (e) {
      console.warn('Error fetching calendar events:', e);
    }
  };

  useEffect(() => {
    fetchMonthEvents();
  }, [currentDate]);

  // Month navigation
  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  const goToToday = () => {
    const today = new Date();
    setCurrentDate(today);
    setSelectedDateStr(today.toISOString().split('T')[0]);
  };

  // Calendar Grid Calculation
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth(); // 0-11
  const monthName = currentDate.toLocaleString('default', { month: 'short' }).toUpperCase();

  const firstDayIndex = new Date(year, month, 1).getDay(); // 0 (Sun) - 6 (Sat)
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  // Event dots mapping for month
  const eventCountsByDate = events.reduce((acc, ev) => {
    if (ev.date) {
      acc[ev.date] = (acc[ev.date] || 0) + 1;
    }
    return acc;
  }, {});

  // Add Event Handler
  const handleAddEvent = async (e) => {
    e.preventDefault();
    if (!newEventTitle.trim()) return;

    try {
      const payload = {
        title: newEventTitle.trim(),
        date: selectedDateStr,
        time: newEventTime || '09:00',
        category: newEventCategory,
        duration_mins: 60,
        set_reminder: true
      };

      const res = await callBackend('save_calendar_event', JSON.stringify(payload));
      if (res && res.status === 'success') {
        setNewEventTitle('');
        setIsAdding(false);
        fetchMonthEvents();
      }
    } catch (err) {
      console.error('Failed to add event:', err);
    }
  };

  // Delete Event
  const handleDeleteEvent = async (eventId) => {
    try {
      await callBackend('delete_calendar_event', eventId);
      setEvents(prev => prev.filter(ev => ev.id !== eventId));
    } catch (err) {
      console.error('Failed to delete event:', err);
    }
  };

  // Toggle Event Status
  const handleToggleStatus = async (eventId) => {
    try {
      const res = await callBackend('toggle_calendar_event', eventId);
      if (res && res.status === 'success' && res.event) {
        setEvents(prev => prev.map(ev => ev.id === eventId ? res.event : ev));
      }
    } catch (err) {
      console.error('Failed to toggle event:', err);
    }
  };

  // Export ICS
  const handleExportICS = async () => {
    try {
      const res = await callBackend('export_calendar_ics');
      if (res && res.status === 'success') {
        setExportNotice('ICS Exported');
        setTimeout(() => setExportNotice(''), 3000);
      }
    } catch (_) {}
  };

  // Launch System / Web Calendar
  const handleOpenCalendarApp = async () => {
    try {
      await callBackend('execute_command', 'open calendar', true);
    } catch (_) {}
  };

  // Events for the currently selected date
  const selectedDayEvents = events.filter(ev => ev.date === selectedDateStr);
  selectedDayEvents.sort((a, b) => (a.time || '00:00').localeCompare(b.time || '00:00'));

  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <div className="panel-content calendar-hub-panel">
      {/* ─── MONTH HEADER & NAVIGATION ─── */}
      <div className="calendar-month-bar">
        <div className="calendar-month-title">
          <CalendarIcon size={14} className="calendar-title-icon" />
          <span>{monthName} {year}</span>
        </div>

        <div className="calendar-nav-actions">
          <button className="cal-nav-btn" onClick={prevMonth} title="Previous Month">
            <ChevronLeft size={14} />
          </button>
          <button className="cal-today-pill" onClick={goToToday} title="Go to Today">
            TODAY
          </button>
          <button className="cal-nav-btn" onClick={nextMonth} title="Next Month">
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* ─── 7-DAY CALENDAR MATRIX GRID ─── */}
      <div className="calendar-grid-container">
        <div className="cal-day-names-row">
          {['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'].map((d) => (
            <div key={d} className="cal-day-header-cell">
              {d}
            </div>
          ))}
        </div>

        <div className="cal-days-grid">
          {/* Previous month filler cells */}
          {Array.from({ length: firstDayIndex }).map((_, i) => {
            const dayNum = daysInPrevMonth - firstDayIndex + i + 1;
            return (
              <div key={`prev-${i}`} className="cal-cell outside-month">
                <span>{dayNum}</span>
              </div>
            );
          })}

          {/* Current month active cells */}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const dayNum = i + 1;
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
            const isSelected = dateStr === selectedDateStr;
            const isToday = dateStr === todayStr;
            const hasEvents = (eventCountsByDate[dateStr] || 0) > 0;

            return (
              <div
                key={dateStr}
                className={`cal-cell ${isSelected ? 'selected' : ''} ${isToday ? 'today' : ''}`}
                onClick={() => setSelectedDateStr(dateStr)}
              >
                <span className="cal-cell-num">{dayNum}</span>
                {hasEvents && <span className="cal-event-dot"></span>}
              </div>
            );
          })}
        </div>
      </div>

      {/* ─── SELECTED DAY AGENDA HEADER ─── */}
      <div className="agenda-section-header">
        <div className="agenda-header-title">
          <Clock size={12} />
          <span>AGENDA — {selectedDateStr}</span>
        </div>
        <button
          className={`agenda-add-btn ${isAdding ? 'active' : ''}`}
          onClick={() => setIsAdding(!isAdding)}
          title="Add Event"
        >
          <Plus size={12} />
          <span>{isAdding ? 'CANCEL' : 'ADD'}</span>
        </button>
      </div>

      {/* ─── INLINE QUICK EVENT CREATOR ─── */}
      {isAdding && (
        <form className="cal-add-event-form" onSubmit={handleAddEvent}>
          <input
            type="text"
            className="cal-input-field"
            placeholder="Event title or meeting..."
            value={newEventTitle}
            onChange={(e) => setNewEventTitle(e.target.value)}
            autoFocus
          />
          <div className="cal-form-row">
            <input
              type="time"
              className="cal-time-input"
              value={newEventTime}
              onChange={(e) => setNewEventTime(e.target.value)}
            />
            <div className="cal-category-selector">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  className={`cal-cat-chip ${newEventCategory === cat ? 'active' : ''}`}
                  onClick={() => setNewEventCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
            <button type="submit" className="cal-submit-btn">
              SAVE
            </button>
          </div>
        </form>
      )}

      {/* ─── AGENDA TIMELINE EVENTS LIST ─── */}
      <div className="agenda-events-list">
        {selectedDayEvents.length > 0 ? (
          selectedDayEvents.map((ev) => (
            <div
              key={ev.id}
              className={`agenda-event-card ${ev.completed ? 'completed' : ''}`}
            >
              <button
                className="event-status-toggle"
                onClick={() => handleToggleStatus(ev.id)}
                title={ev.completed ? 'Mark incomplete' : 'Mark complete'}
              >
                {ev.completed ? (
                  <CheckCircle2 size={15} className="status-checked-icon" />
                ) : (
                  <Circle size={15} className="status-unchecked-icon" />
                )}
              </button>

              <div className="event-info-col">
                <div className="event-top-meta">
                  <span className="event-time-badge">{ev.time || '09:00'}</span>
                  <span className={`event-category-pill cat-${(ev.category || 'WORK').toLowerCase()}`}>
                    {ev.category || 'WORK'}
                  </span>
                </div>
                <div className="event-title-text">{ev.title}</div>
              </div>

              <button
                className="event-delete-btn"
                onClick={() => handleDeleteEvent(ev.id)}
                title="Delete Event"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))
        ) : (
          <div className="agenda-empty-placeholder">
            <span>No events scheduled for this date.</span>
          </div>
        )}
      </div>

      {/* ─── BOTTOM QUICK ACTIONS ─── */}
      <div className="cal-bottom-actions">
        <button
          className="cal-action-btn"
          onClick={handleExportICS}
          title="Export to iCalendar (.ics)"
        >
          <Download size={12} />
          <span>{exportNotice || 'EXPORT ICS'}</span>
        </button>

        <button
          className="cal-action-btn"
          onClick={handleOpenCalendarApp}
          title="Launch System / Outlook Calendar"
        >
          <ExternalLink size={12} />
          <span>LAUNCH APP</span>
        </button>
      </div>
    </div>
  );
};
