/**
 * pywebviewBridge.js
 * Safe bridge wrapper between React and Python's JasvaAPI.
 */

export const isPyWebView = () => {
  return typeof window !== 'undefined' && window.pywebview && window.pywebview.api;
};

export const callBackend = async (methodName, ...args) => {
  if (isPyWebView()) {
    try {
      const api = window.pywebview.api;
      if (typeof api[methodName] === 'function') {
        const res = await api[methodName](...args);
        return typeof res === 'string' ? JSON.parse(res) : res;
      } else {
        console.warn(`[PyWebView] Method ${methodName} not found on api.`);
      }
    } catch (e) {
      console.error(`[PyWebView] Error calling ${methodName}:`, e);
      return { status: 'error', message: String(e) };
    }
  }

  // Fallbacks for testing in standard browser without Python backend
  if (methodName === 'get_settings') {
    return {
      speech_engine: 'edge_tts',
      voice: 'en-GB-RyanNeural',
      volume: 0.75,
      speed: 1.0,
      always_listen: false,
      autostart: false,
      theme: 'default'
    };
  }
  if (methodName === 'get_system_metrics') {
    return {
      cpu: Math.floor(Math.random() * 25 + 10),
      ram: Math.floor(Math.random() * 20 + 40),
      gpu: Math.floor(Math.random() * 15 + 5),
      disk: 45,
      os: 'WINDOWS'
    };
  }
  if (methodName === 'execute_command') {
    return {
      status: 'success',
      reply: `Command executed: "${args[0]}" (Local Simulation Mode)`
    };
  }
  return { status: 'success' };
};
