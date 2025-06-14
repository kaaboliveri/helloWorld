import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';
import MessageList from './components/MessageList';
import MessageInput from './components/MessageInput';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

let messageIdCounter = 2; // Initial messages count + 1 for chat
const BACKEND_WS_URL = process.env.REACT_APP_BACKEND_WS_URL || 'ws://localhost:8000/ws/chat';
const BACKEND_API_URL = process.env.REACT_APP_BACKEND_API_URL || 'http://localhost:8000/api';

const AVAILABLE_MODELS = [
  { id: "claude-3.7-sonnet-20240715", name: "Claude 3.7 Sonnet" },
  { id: "gemini-2.5-pro-preview-03-25", name: "Gemini 2.5 Pro" },
  { id: "o3-mini", name: "OpenAI o3-mini" },
];

function App() {
  const [messages, setMessages] = useState([{ id: 1, text: 'Hello! I am Maity.', sender: 'ai' }]);
  const [conversationId, setConversationId] = useState(() => localStorage.getItem('maityConversationId') || `local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const [isAiTyping, setIsAiTyping] = useState(false);
  const [error, setError] = useState(null);
  const chatWebSocket = useRef(null);
  const [isChatConnected, setIsChatConnected] = useState(false);
  const [selectedModel, setSelectedModel] = useState(AVAILABLE_MODELS[0].id);

  const [monitorTopic, setMonitorTopic] = useState('');
  const [monitorKeywords, setMonitorKeywords] = useState('');
  const [monitorSources, setMonitorSources] = useState('web_search');
  const [monitorFrequency, setMonitorFrequency] = useState(24);
  const [monitorStatusMessage, setMonitorStatusMessage] = useState('');
  const [isSubmittingMonitor, setIsSubmittingMonitor] = useState(false);
  const [activeMonitorTasks, setActiveMonitorTasks] = useState([]);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [selectedTaskResults, setSelectedTaskResults] = useState(null);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [monitoringViewError, setMonitoringViewError] = useState('');

  const [appGenPrompt, setAppGenPrompt] = useState('');
  const [appGenProjectId, setAppGenProjectId] = useState(null);
  const [appGenStatusLog, setAppGenStatusLog] = useState([]);
  const [isGeneratingApp, setIsGeneratingApp] = useState(false);
  const appGenWebSocket = useRef(null);
  const [isAppGenWsConnected, setIsAppGenWsConnected] = useState(false);
  const [appGenError, setAppGenError] = useState('');
  const [generatedAppPlan, setGeneratedAppPlan] = useState(null);
  const [generatedAppPreviewUrl, setGeneratedAppPreviewUrl] = useState(null);

  const [currentView, setCurrentView] = useState('chat');

  useEffect(() => {
    if (currentView === 'chat' && conversationId) {
      localStorage.setItem('maityConversationId', conversationId);
      const wsUrl = `${BACKEND_WS_URL}/${conversationId}`;
      chatWebSocket.current = new WebSocket(wsUrl);
      chatWebSocket.current.onopen = () => { console.log('Chat WebSocket connected'); setIsChatConnected(true); setError(null); };
      chatWebSocket.current.onmessage = (event) => {
        setIsAiTyping(false);
        try {
            const receivedData = JSON.parse(event.data);
            console.log('Chat WS Receive:', receivedData);
            if (receivedData.type === 'error') {
              setError(receivedData.content || 'An error occurred via chat WebSocket.');
              setMessages(prev => [...prev, { id: messageIdCounter++, text: `Error: ${receivedData.content}`, sender: 'ai', isError: true }]);
            } else if (receivedData.type === 'status') {
              if (receivedData.content.toLowerCase().includes("processing") || receivedData.content.toLowerCase().includes("thinking")) setIsAiTyping(true);
            } else if (receivedData.type === 'final_response') {
              const aiResponseMessage = { id: messageIdCounter++, text: receivedData.content, sender: 'ai', isError: receivedData.error || false, debug_info: receivedData.debug_info };
              setMessages(prev => {
                const lastMsg = prev[prev.length -1];
                if (lastMsg && lastMsg.sender === 'ai' && lastMsg.isStreaming && lastMsg.id === (receivedData.message_id || lastMsg.id) ) {
                    return prev.map(msg => msg.id === lastMsg.id ? { ...aiResponseMessage, id: lastMsg.id, isStreaming: false } : msg);
                }
                return [...prev, aiResponseMessage];
              });
            } else if (receivedData.type === 'stream_chunk') {
                setIsAiTyping(true);
                setMessages(prev => {
                    const lastMsg = prev[prev.length - 1];
                    const streamId = receivedData.message_id || (lastMsg && lastMsg.isStreaming ? lastMsg.id : messageIdCounter);
                    if (lastMsg && lastMsg.sender === 'ai' && lastMsg.id === streamId && lastMsg.isStreaming) {
                        return prev.map(msg => msg.id === streamId ? { ...msg, text: (msg.text || "") + receivedData.content } : msg);
                    } else {
                        const newId = (streamId === messageIdCounter && !prev.find(m => m.id === streamId)) ? messageIdCounter++ : streamId;
                        return [...prev, { id: newId, text: receivedData.content, sender: 'ai', isStreaming: true }];
                    }
                });
            } else if (receivedData.type === 'stream_end') {
                 setIsAiTyping(false);
                 setMessages(prev => prev.map(msg => (msg.id === receivedData.message_id || (msg.isStreaming && msg.sender === 'ai' && !receivedData.message_id)) ? {...msg, isStreaming: false} : msg ));
            }
            if (receivedData.conversation_id && receivedData.conversation_id !== conversationId) {
              setConversationId(receivedData.conversation_id);
            }
        } catch (e) { console.error('Error processing chat message:', e); setError('Malformed data from chat server.');}
      };
      chatWebSocket.current.onerror = (err) => { console.error('Chat WebSocket error:', err); setError('Chat WebSocket connection error.'); setIsChatConnected(false); setIsAiTyping(false);};
      chatWebSocket.current.onclose = (event) => { console.log('Chat WebSocket disconnected:', event.reason, `Code: ${event.code}`); setIsChatConnected(false); setIsAiTyping(false);};
      return () => { if (chatWebSocket.current) chatWebSocket.current.close(); };
    } else if (chatWebSocket.current) {
        chatWebSocket.current.close();
        setIsChatConnected(false);
        setIsAiTyping(false);
    }
  }, [conversationId, currentView]);

  useEffect(() => {
    if (currentView === 'appgen' && appGenProjectId) {
      const wsUrl = `ws://localhost:8000/ws/appgen/${appGenProjectId}`;
      appGenWebSocket.current = new WebSocket(wsUrl);
      setAppGenStatusLog(prev => [...prev, {type: 'system', status: 'CONNECTING', message: `Connecting to AppGen status stream for ${appGenProjectId}...`}]);
      setIsAppGenWsConnected(false);

      appGenWebSocket.current.onopen = () => {
        console.log(`AppGen WebSocket connected for project: ${appGenProjectId}`);
        setIsAppGenWsConnected(true);
        setAppGenStatusLog(prev => [...prev, {type: 'system', status: 'CONNECTED', message: 'Connected. Awaiting status updates...'}]);
      };

      appGenWebSocket.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("AppGen Status Update:", data);
          setAppGenStatusLog(prev => [...prev, data]);
          if (data.plan) setGeneratedAppPlan(data.plan);
          if (data.preview_url) setGeneratedAppPreviewUrl(data.preview_url);
          if (data.status === "ERROR") {
            setAppGenError(data.message || "An error occurred during app generation.");
            setIsGeneratingApp(false); // Stop loading on error
          }
          // Example final statuses that might indicate generation is no longer "in progress"
          const finalStatuses = ["EXECUTION_COMPLETE", "PLANNING_SUCCESSFUL_PENDING_CODEGEN", "CODE_GENERATION_ALL_FILES_ATTEMPTED", "ERROR", "CODE_GENERATION_SKIPPED"];
          if (finalStatuses.includes(data.status)) {
             // setIsGeneratingApp(false); // Re-evaluate if this should be here or based on explicit "completed" type message
          }
        } catch (e) {
          console.error("Error processing AppGen status:", e);
          setAppGenStatusLog(prev => [...prev, {type: 'system', status: 'PARSE_ERROR', message: `Error parsing status: ${event.data}`}]);
        }
      };

      appGenWebSocket.current.onerror = (err) => {
        console.error("AppGen WebSocket error:", err);
        setAppGenError('AppGen WebSocket connection error.');
        setIsAppGenWsConnected(false);
        setIsGeneratingApp(false); // Stop loading on WS error
        setAppGenStatusLog(prev => [...prev, {type: 'system', status: 'WS_ERROR', message: 'WebSocket connection error.'}]);
      };

      appGenWebSocket.current.onclose = (event) => {
        console.log(`AppGen WebSocket disconnected (Project: ${appGenProjectId}, Code: ${event.code}, Reason: ${event.reason})`);
        setIsAppGenWsConnected(false);
        // setIsGeneratingApp(false); // Don't automatically stop generation if WS closes unexpectedly, might reconnect or it's still running
        if(!event.wasClean && appGenProjectId) {
             setAppGenStatusLog(prev => [...prev, {type: 'system', status: 'DISCONNECTED', message: 'Status stream disconnected.'}]);
        }
      };
      return () => {
        if (appGenWebSocket.current) {
          appGenWebSocket.current.close();
        }
      };
    } else if (appGenWebSocket.current) {
        appGenWebSocket.current.close();
        setIsAppGenWsConnected(false);
    }
  }, [appGenProjectId, currentView]);

  const handleSendMessage = async (text) => {
    if (currentView !== 'chat' || !chatWebSocket.current || chatWebSocket.current.readyState !== WebSocket.OPEN) { setError('Not connected to Maity AI for chat.'); return; }
    const newUserMessage = { id: messageIdCounter++, text: text, sender: 'user' };
    setMessages(prev => [...prev, newUserMessage]);
    setIsAiTyping(true); setError(null);
    chatWebSocket.current.send(JSON.stringify({ message: text, config: { preferred_model: selectedModel } }));
  };
  useEffect(() => { const el = document.querySelector('.message-list'); if (el) el.scrollTop = el.scrollHeight; }, [messages]);
  useEffect(() => { const el = document.querySelector('.appgen-status-log'); if (el) el.scrollTop = el.scrollHeight; }, [appGenStatusLog]);


  const handleNewChat = () => {
    if (chatWebSocket.current && chatWebSocket.current.readyState === WebSocket.OPEN) chatWebSocket.current.close();
    setCurrentView('chat');
    setMessages([{ id: 1, text: 'New chat. Select model and ask.', sender: 'ai' }]);
    setConversationId(`local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
    setIsAiTyping(false); setError(null); messageIdCounter = 2;
  };

  const handleModelChange = (event) => {
    const newModelId = event.target.value;
    setSelectedModel(newModelId);
    if (currentView === 'chat') {
        setMessages(prev => [...prev, { id: messageIdCounter++, text: `Switched to ${AVAILABLE_MODELS.find(m=>m.id === newModelId)?.name}.`, sender: 'ai', isSystemInfo: true }]);
    }
  };

  const handleSetupMonitorSubmit = async (event) => {
    event.preventDefault();
    setIsSubmittingMonitor(true); setMonitorStatusMessage('');
    try {
      const payload = { topic: monitorTopic, keywords: monitorKeywords, sources: monitorSources, frequency_hours: parseInt(monitorFrequency, 10) };
      if (isNaN(payload.frequency_hours) || payload.frequency_hours <= 0) { setMonitorStatusMessage('Error: Frequency must be a number greater than 0.'); setIsSubmittingMonitor(false); return; }
      const response = await axios.post(`${BACKEND_API_URL}/monitor/setup`, payload);
      setMonitorStatusMessage(`Success: ${response.data.message}`);
      fetchActiveMonitorTasks();
    } catch (err) {
      let errorMsg = 'Failed to set up monitoring task.';
      if (err.response && err.response.data && err.response.data.detail) errorMsg = `Error: ${err.response.data.detail}`;
      else if (err.message) errorMsg = `Error: ${err.message}`;
      setMonitorStatusMessage(errorMsg);
      console.error("Error setting up monitor:", err);
    }
    finally { setIsSubmittingMonitor(false); }
  };

  const fetchActiveMonitorTasks = async () => { /* ... as before ... */ };
  const fetchTaskResults = async (taskId) => { /* ... as before ... */ };
  useEffect(() => { if (currentView === 'monitoring') fetchActiveMonitorTasks(); }, [currentView]);

  const handleGenerateApp = async () => {
    if (!appGenPrompt.trim()) { setAppGenError("Please enter a prompt for your application."); return; }
    setIsGeneratingApp(true); setAppGenError(''); setAppGenStatusLog([]); setGeneratedAppPlan(null); setGeneratedAppPreviewUrl(null); setAppGenProjectId(null); // Reset project ID to allow new generation
    if (appGenWebSocket.current) appGenWebSocket.current.close();

    try {
      const response = await axios.post(`${BACKEND_API_URL}/app/generate`, { prompt: appGenPrompt });
      if (response.data && response.data.project_id) {
        setAppGenStatusLog([{type: 'system', status: 'INITIATED', message: `App generation started. ${response.data.initial_message}`}]);
        setAppGenProjectId(response.data.project_id); // This triggers useEffect for WebSocket
      } else { throw new Error("Backend did not return a project_id."); }
    } catch (err) {
      let errorMsg = 'Failed to start app generation.';
      if (err.response && err.response.data && err.response.data.detail) errorMsg = `Error: ${err.response.data.detail}`;
      else if (err.message) errorMsg = `Error: ${err.message}`;
      setAppGenError(errorMsg); console.error("Error starting app generation:", err);
      setIsGeneratingApp(false);
    }
  };

  const renderChatView = () => (
    <div className="chat-view-container">
      <div className="chat-window">
        {!isChatConnected && !error && currentView === 'chat' && <div className="connection-indicator">Connecting to Chat...</div>}
        {error && <div className="error-indicator">{error}</div>}
        <MessageList messages={messages} />
        {isAiTyping && <div className="typing-indicator">Maity is thinking...</div>}
        <MessageInput onSendMessage={handleSendMessage} isAiTyping={isAiTyping || (currentView === 'chat' && !isChatConnected)} />
      </div>
    </div>
  );
  const renderMonitoringView = () => ( /* ... as before, ensure all states are defined ... */
      <div className="monitoring-view-container">
          <div className="monitor-section">
            <h2>Setup New Monitoring Task</h2>
            <form onSubmit={handleSetupMonitorSubmit} className="monitor-setup-form">
              <div className="form-group"> <label htmlFor="monitorTopic">Topic:</label> <input type="text" id="monitorTopic" value={monitorTopic} onChange={(e) => setMonitorTopic(e.target.value)} required /> </div>
              <div className="form-group"> <label htmlFor="monitorKeywords">Keywords:</label> <input type="text" id="monitorKeywords" value={monitorKeywords} onChange={(e) => setMonitorKeywords(e.target.value)} required /> </div>
              <div className="form-group"> <label htmlFor="monitorSources">Sources:</label> <select id="monitorSources" value={monitorSources} onChange={(e) => setMonitorSources(e.target.value)}><option value="web_search">Web Search</option></select> </div>
              <div className="form-group"> <label htmlFor="monitorFrequency">Frequency (hrs):</label> <input type="number" id="monitorFrequency" value={monitorFrequency} onChange={(e) => setMonitorFrequency(Number(e.target.value))} min="1" required /> </div>
              <button type="submit" className="submit-monitor-button" disabled={isSubmittingMonitor}> {isSubmittingMonitor ? 'Setting up...' : 'Setup Monitoring Task'} </button>
              {monitorStatusMessage && (<div className={`monitor-status-message ${monitorStatusMessage.includes('Error:') ? 'error' : 'success'}`}>{monitorStatusMessage}</div>)}
            </form>
          </div>
          <div className="monitor-section">
            <h2>Active Monitoring Tasks</h2>
            <button onClick={fetchActiveMonitorTasks} disabled={isLoadingTasks} className="refresh-tasks-button">{isLoadingTasks ? 'Refreshing...' : 'Refresh Active Tasks'}</button>
            {monitoringViewError && !isLoadingTasks && <div className="monitor-error-message">{monitoringViewError}</div>}
            {isLoadingTasks && <p>Loading tasks...</p>}
            {!isLoadingTasks && activeMonitorTasks.length === 0 && !monitoringViewError && <p>No active monitoring tasks found.</p>}
            {activeMonitorTasks.length > 0 && (
              <ul className="monitor-task-list">
                {activeMonitorTasks.map(task => (
                  <li key={task.id} className="monitor-task-item">
                    <div className="task-info"><strong>ID:</strong> {task.id} <br /><strong>Topic:</strong> {task.topic} <br /><strong>Frequency:</strong> {task.frequency_hours}h <br /><strong>Next Run:</strong> {task.next_run ? new Date(task.next_run).toLocaleString() : 'N/A'}</div>
                    <button onClick={() => fetchTaskResults(task.id)} disabled={isLoadingResults && selectedTaskResults?.taskId === task.id} className="view-results-button">{isLoadingResults && selectedTaskResults?.taskId === task.id ? 'Loading...' : 'View Results'}</button>
                    {selectedTaskResults && selectedTaskResults.taskId === task.id && (
                      <div className="task-results-display"><h4>Results for: {task.topic}</h4>{selectedTaskResults.isError && <p className="error-text">{selectedTaskResults.message}</p>}{!selectedTaskResults.isError && selectedTaskResults.results.length === 0 && <p>{selectedTaskResults.message || "No results available."}</p>}{selectedTaskResults.results.length > 0 && (<ul>{selectedTaskResults.results.map((finding, index) => (<li key={index} className="finding-item">{finding.timestamp && <span className="finding-timestamp">{new Date(finding.timestamp).toLocaleString()}: </span>}<div className="finding-title"><ReactMarkdown remarkPlugins={[remarkGfm]}>{finding.title || 'N/A'}</ReactMarkdown></div>{finding.source_url && <a href={finding.source_url} target="_blank" rel="noopener noreferrer" className="finding-source"> (Source)</a>}</li>))}</ul>)}</div>)}
                  </li>))}</ul>)}
          </div>
        </div>
  );

  const renderAppGeneratorView = () => (
    <div className="appgen-view-container">
      <h2>Application Generator</h2>
      <div className="appgen-form-section">
        <textarea value={appGenPrompt} onChange={(e) => setAppGenPrompt(e.target.value)} placeholder="Describe the application you want to generate..." rows="5" className="appgen-prompt-input" disabled={isGeneratingApp} />
        <button onClick={handleGenerateApp} disabled={isGeneratingApp || !appGenPrompt.trim()} className="appgen-submit-button">
          {isGeneratingApp ? 'Generating...' : 'Generate Application'}
        </button>
        {appGenError && <div className="appgen-error-message">{appGenError}</div>}
      </div>

      {appGenProjectId && (
        <div className="appgen-status-section">
          <h3>Generation Status (Project ID: {appGenProjectId})</h3>
          {!isAppGenWsConnected && appGenProjectId && !appGenError && <p className="connection-indicator">Connecting to status stream...</p>}
          <div className="appgen-status-log">
            {appGenStatusLog.map((logEntry, index) => (
              <div key={index} className={`log-entry log-type-${logEntry.type || 'status'} log-status-${logEntry.status?.toLowerCase() || 'unknown'}`}>
                <strong>{logEntry.status || logEntry.type?.toUpperCase()}:</strong> {logEntry.message}
                {logEntry.current_file && ` (File: ${logEntry.current_file})`}
                {logEntry.error_details && <pre className="error-details">{logEntry.error_details}</pre>}
              </div>
            ))}
          </div>
          {generatedAppPlan && (
            <div className="appgen-plan-display"><h4>Generated Plan:</h4><p><strong>Stack:</strong> {JSON.stringify(generatedAppPlan.stack)}</p><p><strong>Components:</strong> {generatedAppPlan.components_description}</p><p><strong>Data Models:</strong> {generatedAppPlan.data_models_description}</p><p><strong>Files:</strong></p><pre>{JSON.stringify(generatedAppPlan.files, null, 2)}</pre></div>
          )}
          {generatedAppPreviewUrl && (<div className="appgen-preview-url"><h4>Preview URL:</h4><a href={generatedAppPreviewUrl} target="_blank" rel="noopener noreferrer">{generatedAppPreviewUrl}</a></div>)}
        </div>
      )}
    </div>
  );

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="app-title-area"><h1>Maity AI</h1></div>
        <nav className="app-navigation">
            <button onClick={() => setCurrentView('chat')} className={currentView === 'chat' ? 'active' : ''}>Chat</button>
            <button onClick={() => setCurrentView('monitoring')} className={currentView === 'monitoring' ? 'active' : ''}>Monitoring</button>
            <button onClick={() => setCurrentView('appgen')} className={currentView === 'appgen' ? 'active' : ''}>App Generator</button>
        </nav>
        <div className="header-controls">
            {currentView === 'chat' && ( <> <select className="model-selector" value={selectedModel} onChange={handleModelChange} title="Select Model"> {AVAILABLE_MODELS.map(model => (<option key={model.id} value={model.id}>{model.name}</option>))} </select> <button onClick={handleNewChat} className="new-chat-button" title="Start New Chat">New Chat</button> </> )}
            {(currentView === 'monitoring' || currentView === 'appgen') && (<div className="header-placeholder" style={{minWidth:'220px'}}></div>)}
        </div>
      </header>

      {currentView === 'chat' && renderChatView()}
      {currentView === 'monitoring' && renderMonitoringView()}
      {currentView === 'appgen' && renderAppGeneratorView()}

    </div>
  );
}
export default App;
