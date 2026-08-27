import React, { useState } from 'react';
import { useJasva } from '../context/JasvaContext';
import {
  Search,
  BookOpen,
  Lightbulb,
  CheckCircle,
  Terminal,
  AlertCircle,
  ChevronDown,
  Zap,
  Brain,
  Loader
} from 'lucide-react';

const STEP_ICONS = {
  start: Zap,
  thought: Brain,
  action: Terminal,
  observation: BookOpen,
  stream_start: Loader,
  stream_end: CheckCircle,
  stop: CheckCircle,
};

const STEP_LABELS = {
  start: 'INITIALIZING',
  thought: 'REASONING',
  action: 'EXECUTING',
  observation: 'OBSERVING',
  stream_start: 'STREAMING',
  stream_end: 'STREAM COMPLETE',
  stop: 'COMPLETE',
};

const STEP_COLORS = {
  start: 'var(--accent-color)',
  thought: '#bd00ff',
  action: '#ff8800',
  observation: '#4facfe',
  stream_start: 'var(--accent-color)',
  stream_end: '#00ff87',
  stop: '#00ff87',
};

export const AgentTrace = () => {
  const { agentTrace } = useJasva();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!agentTrace.steps.length || (agentTrace.steps.length === 1 && agentTrace.steps[0].type === 'stop')) {
    return null;
  }

  // Only show the last few steps to keep it compact
  const visibleSteps = isExpanded ? agentTrace.steps : agentTrace.steps.slice(-4);

  return (
    <div className="agent-trace-container">
      <div
        className="agent-trace-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="agent-trace-title">
          {agentTrace.active ? (
            <Loader size={12} className="spinning" />
          ) : (
            <CheckCircle size={12} color="#00ff87" />
          )}
          <span>AGENT {agentTrace.active ? 'WORKING' : 'COMPLETE'}</span>
          {agentTrace.currentStep && (
            <span className="agent-trace-step-label">
              {agentTrace.currentStep.slice(0, 40)}
            </span>
          )}
        </div>
        <ChevronDown
          size={11}
          style={{
            transform: isExpanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s ease',
            opacity: 0.5
          }}
        />
      </div>

      {/* Step Timeline */}
      <div className="agent-trace-steps">
        {visibleSteps.map((step, idx) => {
          const Icon = STEP_ICONS[step.type] || Zap;
          const label = STEP_LABELS[step.type] || step.type;
          const color = STEP_COLORS[step.type] || 'var(--accent-color)';

          return (
            <div key={idx} className="agent-trace-step">
              <div className="agent-step-icon" style={{ color }}>
                <Icon size={10} />
              </div>
              <div className="agent-step-content">
                <span className="agent-step-type" style={{ color }}>{label}</span>
                {step.data?.command && (
                  <span className="agent-step-detail">{step.data.command}</span>
                )}
                {step.data?.output && (
                  <span className="agent-step-output">{step.data.output.slice(0, 100)}</span>
                )}
                {step.type === 'thought' && step.data?.thought && (
                  <span className="agent-step-detail">{step.data.thought.slice(0, 120)}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Plan Progress Bar */}
      {agentTrace.plan.length > 0 && isExpanded && (
        <div className="agent-trace-plan">
          {agentTrace.plan.map((step, idx) => {
            const isDone = step.includes('[Done]') || step.includes('[done]');
            const isActive = step.includes('[Active]') || step.includes('[active]');
            return (
              <div
                key={idx}
                className={`agent-plan-step ${isDone ? 'done' : isActive ? 'active' : 'pending'}`}
              >
                {isDone ? <CheckCircle size={9} /> : isActive ? <Loader size={9} className="spinning" /> : <span className="plan-dot" />}
                <span>{step.replace(/\[(Done|Active|Pending|done|active|pending)\]/g, '').trim()}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
