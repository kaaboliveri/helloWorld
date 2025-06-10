import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import MessageList from './components/MessageList';
import MessageInput from './components/MessageInput';

let messageIdCounter = 2; // Adjusted as initial messages changed
const BACKEND_WS_URL = process.env.REACT_APP_BACKEND_WS_URL || 'ws://localhost:8000/ws/chat';

// Define available models - values should match model IDs expected by backend (config.py, llm_clients.py)
const AVAILABLE_MODELS = [
  { id: "claude-3.7-sonnet-20240715", name: "Claude 3.7 Sonnet" },
  { id: "gemini-2.5-pro-preview-03-25", name: "Gemini 2.5 Pro" },
  { id: "o3-mini", name: "OpenAI o3-mini" }, // Ensure this ID is correct as per backend config
];

function App() {
  const [messages, setMessages] = useState([
    { id: 1, text: 'Hello! I am Maity. Select a model and ask me anything.', sender: 'ai' },
  ]);
  const [conversationId, setConversationId] = useState(() => {
    const savedCid = localStorage.getItem('maityConversationId');
    return savedCid || `local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  });
  const [isAiTyping, setIsAiTyping] = useState(false);
  const [error, setError] = useState(null);
  const webSocket = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedModel, setSelectedModel] = useState(AVAILABLE_MODELS[0].id); // Default to first model

  useEffect(() => {
    if (conversationId) {
      localStorage.setItem('maityConversationId', conversationId);
    }
  }, [conversationId]);

  useEffect(() => {
    if (!conversationId) return;

    console.log(`Attempting to connect WebSocket for conversation: ${conversationId}`);
    const wsUrl = `${BACKEND_WS_URL}/${conversationId}`;
    webSocket.current = new WebSocket(wsUrl);

    webSocket.current.onopen = () => {
      console.log('WebSocket connected to:', wsUrl);
      setIsConnected(true);
      setError(null);
    };

    webSocket.current.onmessage = (event) => {
      setIsAiTyping(false);
      try {
        const receivedData = JSON.parse(event.data);
        console.log('WebSocket message received:', receivedData);

        if (receivedData.type === 'error') {
          setError(receivedData.content || 'An error occurred via WebSocket.');
          const errorMessage = {
            id: messageIdCounter++,
            text: `Error: ${receivedData.content}`,
            sender: 'ai',
            isError: true,
          };
          setMessages(prevMessages => [...prevMessages, errorMessage]);
        } else if (receivedData.type === 'status') {
          console.log("Status update:", receivedData.content);
          if (receivedData.content.toLowerCase().includes("processing") || receivedData.content.toLowerCase().includes("thinking")) {
            setIsAiTyping(true);
          }
        } else if (receivedData.type === 'final_response') {
          const aiResponseMessage = {
            id: messageIdCounter++, // Ensure new ID for final response
            text: receivedData.content,
            sender: 'ai',
            isError: receivedData.error || false,
            debug_info: receivedData.debug_info
          };
          // If last message was streaming, update it, else add new.
          setMessages(prevMessages => {
            const lastMessage = prevMessages[prevMessages.length -1];
            if (lastMessage && lastMessage.sender === 'ai' && lastMessage.isStreaming) {
                // If the final response corresponds to an ongoing stream, update it.
                // This assumes the stream_end might not always come or this is a consolidated final message.
                return prevMessages.map(msg =>
                    msg.id === lastMessage.id ? { ...aiResponseMessage, id: lastMessage.id, isStreaming: false } : msg
                );
            }
            return [...prevMessages, aiResponseMessage];
          });
        } else if (receivedData.type === 'stream_chunk') {
            setIsAiTyping(true);
            setMessages(prevMessages => {
                const lastMessage = prevMessages[prevMessages.length - 1];
                const streamMessageId = receivedData.message_id || (lastMessage && lastMessage.isStreaming ? lastMessage.id : messageIdCounter);

                if (lastMessage && lastMessage.sender === 'ai' && lastMessage.id === streamMessageId && lastMessage.isStreaming) {
                    return prevMessages.map(msg =>
                        msg.id === streamMessageId ? { ...msg, text: (msg.text || "") + receivedData.content, isStreaming: true } : msg
                    );
                } else {
                    // Start a new AI message for streaming
                    const newStreamId = (streamMessageId === messageIdCounter && !prevMessages.find(m => m.id === streamMessageId)) ? messageIdCounter++ : streamMessageId;
                    return [
                        ...prevMessages,
                        { id: newStreamId, text: receivedData.content, sender: 'ai', isStreaming: true }
                    ];
                }
            });
        } else if (receivedData.type === 'stream_end') {
             setIsAiTyping(false);
             setMessages(prevMessages => prevMessages.map(msg =>
                (msg.id === receivedData.message_id || (msg.isStreaming && msg.sender === 'ai' && !receivedData.message_id))
                ? {...msg, isStreaming: false} : msg
             ));
        }

        if (receivedData.conversation_id && receivedData.conversation_id !== conversationId) {
          setConversationId(receivedData.conversation_id);
        }

      } catch (e) {
        console.error('Error processing WebSocket message:', e);
        setError('Received malformed data from server.');
      }
    };

    webSocket.current.onerror = (err) => {
      console.error('WebSocket error:', err);
      setError('WebSocket connection error. Please try refreshing.');
      setIsAiTyping(false);
      setIsConnected(false);
    };

    webSocket.current.onclose = (event) => {
      console.log('WebSocket disconnected:', event.reason, `Code: ${event.code}`);
      setIsConnected(false);
    };

    return () => {
      if (webSocket.current) {
        console.log("Closing WebSocket connection");
        webSocket.current.close();
      }
    };
  }, [conversationId]);

  const handleSendMessage = async (text) => {
    if (!webSocket.current || webSocket.current.readyState !== WebSocket.OPEN) {
      setError('Not connected to Maity AI. Please wait or refresh.');
      return;
    }

    const newUserMessage = {
      id: messageIdCounter++,
      text: text,
      sender: 'user',
    };
    setMessages(prevMessages => [...prevMessages, newUserMessage]);
    setIsAiTyping(true);
    setError(null);

    try {
      const messagePayload = {
        message: text,
        config: { preferred_model: selectedModel } // Include selected model
      };
      webSocket.current.send(JSON.stringify(messagePayload));
      console.log('WebSocket message sent:', messagePayload);
    } catch (err) {
      console.error('Error sending message via WebSocket:', err);
      setError('Failed to send message. Check connection.');
      setIsAiTyping(false);
    }
  };

  useEffect(() => {
    const messageList = document.querySelector('.message-list');
    if (messageList) {
      messageList.scrollTop = messageList.scrollHeight;
    }
  }, [messages]);

  const handleNewChat = () => {
    if (webSocket.current) {
      webSocket.current.close();
    }
    setMessages([{ id: 1, text: 'New chat started. Select a model and how can I help?', sender: 'ai' }]);
    setConversationId(`local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
    setIsAiTyping(false);
    setError(null);
    messageIdCounter = 2;
  };

  const handleModelChange = (event) => {
    const newModelId = event.target.value;
    setSelectedModel(newModelId);
    setMessages(prev => [...prev, {
        id: messageIdCounter++,
        text: `Switched to ${AVAILABLE_MODELS.find(m => m.id === newModelId)?.name}.`,
        sender: 'ai',
        isSystemInfo: true,
    }]);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Maity AI Chat</h1>
        <div className="header-controls">
          <select className="model-selector" value={selectedModel} onChange={handleModelChange} title="Select AI Model">
            {AVAILABLE_MODELS.map(model => (
              <option key={model.id} value={model.id}>{model.name}</option>
            ))}
          </select>
          <button onClick={handleNewChat} className="new-chat-button" title="Start a new chat session">New Chat</button>
        </div>
      </header>
      <div className="chat-window">
        {!isConnected && !error && <div className="connection-indicator">Connecting to Maity...</div>}
        {error && <div className="error-indicator">{error}</div>}
        <MessageList messages={messages} />
        {isAiTyping && <div className="typing-indicator">Maity is thinking...</div>}
        <MessageInput onSendMessage={handleSendMessage} isAiTyping={isAiTyping || !isConnected} />
      </div>
    </div>
  );
}

export default App;
