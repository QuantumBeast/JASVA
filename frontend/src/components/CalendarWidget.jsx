import React, { useState, useEffect } from 'react';
import { DraggableWidget } from './DraggableWidget';
import { callBackend } from '../utils/pywebviewBridge';
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Plus,
  RefreshCw,
  Layers,
  Globe,
  Trash2,
  Clock,
  Sparkles
} from 'lucide-react';

export const CalendarWidget = ({ initialPos = { x: 40, y: 310 } }) => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDateStr, setSelectedDateStr] = useState(() => new Date().toISOString().split('T')[0]);
  const [events, setEvents] = useState([]);
  const [feeds, setFeeds] = useState([]);
  const [isAdding, setIsAdding] = useState(false);
  const [isLinking, setIsLinking] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newFeedName, setNewFeedName] = useState('');
  const [newFeedUrl, setNewFeedUrl] = useState('');
  const [newFeedColor, setNewFeedColor] = useState('#00f2fe');
  const [isSyncing, setIsSyncing] = useState(false);

  const fetchAllCalendarData = async () => {
    try {
      const allEvents = await callBackend('get_calendar_events', '');
      if (Array.isArray(allEvents)) setEvents(allEvents);

      const feedList = await callBackend('get_calendar_feeds');
      if (Array.isArray(feedList)) setFeeds(feedList);
    } catch (_) {}
  };

  useEffect(() => {
    let mounted = true;
    fetchAllCalendarData();
    // Background polling interval so new synced events appear automatically without manual refresh
    const interval = setInterval(() => {
      if (mounted) fetchAllCalendarData();
    }, 15000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleSyncAll = async () => {
    setIsSyncing(true);
    try {
      await callBackend('sync_google_calendar');
      await fetchAllCalendarData();
    } catch (_) {}
    setTimeout(() => setIsSyncing(false), 800);
  };

  const handleAddFeed = async (e) => {
    e.preventDefault();
    if (!newFeedUrl.trim()) return;
    setIsSyncing(true);
    try {
      await callBackend('add_calendar_feed', JSON.stringify({
        name: newFeedName.trim() || `Calendar ${feeds.length + 1}`,
        url: newFeedUrl.trim(),
        color: newFeedColor
      }));
      setNewFeedName('');
      setNewFeedUrl('');
      await fetchAllCalendarData();
    } catch (_) {}
    setIsSyncing(false);
  };

  const handleRemoveFeed = async (feedId) => {
    setIsSyncing(true);
    try {
      await callBackend('remove_calendar_feed', feedId);
      await fetchAllCalendarData();
    } catch (_) {}
    setIsSyncing(false);
  };

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const monthName = currentDate.toLocaleString('default', { month: 'short' }).toUpperCase();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDay = new Date(year, month, 1).getDay();
  const todayStr = new Date().toISOString().split('T')[0];

  const handleAddEvent = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    try {
      await callBackend('save_calendar_event', JSON.stringify({
        title: newTitle.trim(),
        date: selectedDateStr,
        time: '09:00',
        category: 'WORK'
      }));
      setNewTitle('');
      setIsAdding(false);
      fetchAllCalendarData();
    } catch (_) {}
  };

  // Events on the currently selected day
  const selectedDayEvents = events.filter(e => e.date === selectedDateStr);

  return (
    <DraggableWidget
      id="calendar"
      title="CALENDAR"
      icon={CalendarIcon}
      initialPos={initialPos}
      width={310}
    >
      <div className="calendar-widget-content">
        {/* Multi-Calendar Sync Header */}
        <div className="cal-sync-status-row">
          <div className="cal-status-pill">
            <span className={`cal-sync-dot ${feeds.length > 0 ? 'online' : ''}`}></span>
            <span className="cal-sync-label">
              {feeds.length > 0 ? `${feeds.length} SYNCED` : 'LOCAL'}
            </span>
          </div>

          <div className="cal-status-tools">
            <button
              className={`cal-mini-icon-btn ${isSyncing ? 'spinning' : ''}`}
              onClick={handleSyncAll}
              title="Sync Google Calendars"
            >
              <RefreshCw size={11} />
            </button>
            <button
              className={`cal-mini-icon-btn ${isLinking ? 'active' : ''}`}
              onClick={() => setIsLinking(!isLinking)}
              title="Manage Calendars (Birthdays, Work, etc.)"
            >
              <Layers size={11} />
            </button>
            <button
              className="cal-mini-icon-btn"
              onClick={() => setIsAdding(!isAdding)}
              title="Add Event"
            >
              <Plus size={11} />
            </button>
          </div>
        </div>

        {/* Multi-Calendar Drawer */}
        {isLinking && (
          <div className="cal-link-drawer">
            <div className="cal-drawer-title">
              <Globe size={11} />
              <span>CALENDARS ({feeds.length})</span>
            </div>

            <div className="cal-feeds-list">
              {feeds.map(f => (
                <div key={f.id} className="cal-feed-row">
                  <div className="cal-feed-meta">
                    <span className="cal-feed-dot" style={{ backgroundColor: f.color || '#00f2fe' }}></span>
                    <span className="cal-feed-name" title={f.name}>{f.name}</span>
                  </div>
                  <button
                    className="cal-feed-del-btn"
                    onClick={() => handleRemoveFeed(f.id)}
                    title={`Remove ${f.name}`}
                  >
                    <Trash2 size={10} />
                  </button>
                </div>
              ))}
              {feeds.length === 0 && (
                <div className="cal-feeds-empty">No calendars linked.</div>
              )}
            </div>

            <form onSubmit={handleAddFeed} className="cal-feed-add-form">
              <div className="cal-feed-inputs-row">
                <input
                  type="text"
                  placeholder="Name (e.g. Birthdays)"
                  value={newFeedName}
                  onChange={(e) => setNewFeedName(e.target.value)}
                  className="cal-feed-input name"
                />
                <select
                  value={newFeedColor}
                  onChange={(e) => setNewFeedColor(e.target.value)}
                  className="cal-color-picker-select"
                  style={{ color: newFeedColor }}
                >
                  <option value="#00f2fe">CYAN</option>
                  <option value="#ff3b30">RED (BDAYS)</option>
                  <option value="#00ff87">GREEN</option>
                  <option value="#c026d3">PURPLE</option>
                  <option value="#ff8800">ORANGE</option>
                </select>
              </div>

              <div className="cal-link-form">
                <input
                  type="text"
                  placeholder="Secret iCal Link..."
                  value={newFeedUrl}
                  onChange={(e) => setNewFeedUrl(e.target.value)}
                  className="cal-link-input"
                />
                <button type="submit" className="cal-link-submit" disabled={isSyncing}>
                  {isSyncing ? '...' : '+ LINK'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Month Navigation */}
        <div className="cal-widget-month-row">
          <button className="cal-icon-btn" onClick={() => setCurrentDate(new Date(year, month - 1, 1))}>
            <ChevronLeft size={13} />
          </button>
          <span
            className="cal-month-label"
            onClick={() => {
              setSelectedDateStr(todayStr);
              setCurrentDate(new Date());
            }}
            style={{ cursor: 'pointer' }}
            title="Click to jump to Current Month"
          >
            {monthName} {year}
          </span>
          <button className="cal-icon-btn" onClick={() => setCurrentDate(new Date(year, month + 1, 1))}>
            <ChevronRight size={13} />
          </button>
        </div>

        {/* 7-Day Matrix with Direct Event Indicators */}
        <div className="cal-widget-matrix pure-matrix-only">
          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
            <div key={i} className="cal-w-day-name">{d}</div>
          ))}
          {Array.from({ length: firstDay }).map((_, i) => (
            <div key={`empty-${i}`} className="cal-w-cell empty"></div>
          ))}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const dNum = i + 1;
            const dStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(dNum).padStart(2, '0')}`;
            const isSel = dStr === selectedDateStr;
            const isTod = dStr === todayStr;
            const dayEvs = events.filter(e => e.date === dStr);
            const hasEv = dayEvs.length > 0;
            const primaryColor = dayEvs[0]?.feed_color || (dayEvs[0]?.category === 'BIRTHDAY' ? '#ff3b30' : '#00f2fe');

            return (
              <div
                key={dStr}
                className={`cal-w-cell ${isSel ? 'selected' : ''} ${isTod ? 'today' : ''} ${hasEv ? 'has-events' : ''}`}
                onClick={() => setSelectedDateStr(dStr)}
                title={hasEv ? `${dStr}: ${dayEvs.map(e => e.title).join(' | ')}` : dStr}
              >
                <span className="cal-w-num">{dNum}</span>
                {hasEv && (
                  <div className="cal-w-dots-cluster">
                    {dayEvs.slice(0, 3).map((ev, idx) => {
                      const dotColor = ev.feed_color || (ev.category === 'BIRTHDAY' ? '#ff3b30' : '#00f2fe');
                      return (
                        <span
                          key={idx}
                          className="cal-w-dot"
                          style={{
                            backgroundColor: isSel ? '#000' : dotColor,
                            boxShadow: isSel ? 'none' : `0 0 5px ${dotColor}`
                          }}
                        ></span>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Selected Date Popup Ribbon (Only when events exist on selected date) */}
        {selectedDayEvents.length > 0 && (
          <div className="cal-day-event-banner">
            <div className="cal-banner-header">
              <span className="cal-banner-date">{selectedDateStr}</span>
              <span className="cal-banner-count">{selectedDayEvents.length} EVENT{selectedDayEvents.length > 1 ? 'S' : ''}</span>
            </div>
            {selectedDayEvents.map((ev, i) => {
              const tagColor = ev.feed_color || (ev.category === 'BIRTHDAY' ? '#ff3b30' : '#00f2fe');
              return (
                <div key={i} className="cal-banner-item">
                  <span className="cal-banner-dot" style={{ backgroundColor: tagColor }}></span>
                  <span className="cal-banner-time">{ev.time || '09:00'}</span>
                  <span className="cal-banner-title">{ev.title}</span>
                  {ev.category === 'BIRTHDAY' && <span>🎂</span>}
                </div>
              );
            })}
          </div>
        )}

        {/* Inline Add Event form */}
        {isAdding && (
          <form className="cal-widget-add-form" onSubmit={handleAddEvent}>
            <input
              type="text"
              placeholder="Event title on selected day..."
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="cal-w-input"
              autoFocus
            />
            <button type="submit" className="cal-w-submit">ADD</button>
          </form>
        )}
      </div>
    </DraggableWidget>
  );
};
