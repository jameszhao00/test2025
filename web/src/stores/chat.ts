import { ref, computed, nextTick } from 'vue'
import { defineStore } from 'pinia'
import { v4 as uuidv4 } from 'uuid' // Import uuid
import {
  DefaultApi,
  Configuration,
  ResponseError,
  type ChatMessage, // This type will lack 'id' after regeneration
  type ChatRequest,
  type FetchMessagesResponse,
  type TextContent,
} from '@/api-client'

// --- Constants ---
const SESSION_ID_STORAGE_KEY = 'chatSessionId'
const LOG_PREFIX = '[ChatStore]'

// --- API Client Setup ---
const config = new Configuration({ basePath: '' })
const apiClient = new DefaultApi(config)

// --- Augment ChatMessage type locally for client-side key ---
// We add a non-enumerable _clientId property
interface ClientChatMessage extends ChatMessage {
  _clientId: string // Unique key for Vue list rendering
}

// --- Store Definition ---
export const useChatStore = defineStore('chat', () => {
  // --- State ---
  const messages = ref<ClientChatMessage[]>([]) // Use augmented type
  const sessionId = ref<string | null>(localStorage.getItem(SESSION_ID_STORAGE_KEY))
  const error = ref<string | null>(null)
  const isLoading = ref<boolean>(false) // Loading state for sending messages
  const isConnecting = ref<boolean>(false) // Initial connection/loading state
  // lastMessageId removed

  // --- Getters (Computed Properties) ---
  const hasSession = computed(() => !!sessionId.value)

  // --- Private Helper Functions ---
  async function _getErrorMessage(e: unknown, defaultMessage: string): Promise<string> {
    console.error(`${LOG_PREFIX} Error encountered: ${defaultMessage}`, e)
    // ... (error formatting logic remains the same) ...
    if (e instanceof ResponseError) {
      try {
        const errorBody = await e.response.json()
        console.error(`${LOG_PREFIX} Parsed error response body:`, errorBody)
        if (errorBody.detail) {
          if (Array.isArray(errorBody.detail)) {
            return errorBody.detail
              .map((d: any) => `${d.loc?.join('.') ?? 'error'} - ${d.msg}`)
              .join('; ')
          }
          return String(errorBody.detail)
        }
        return `${e.response.status}: ${e.response.statusText || defaultMessage}`
      } catch (parseError) {
        console.error(`${LOG_PREFIX} Failed to parse error response:`, parseError)
        return `${e.response.status}: ${e.response.statusText || defaultMessage}`
      }
    } else if (e instanceof Error) {
      return e.message
    }
    return defaultMessage
  }

  // _updateLastMessageId removed

  // --- Internal Helper to Add Message with Client ID ---
  function _addClientMessage(messageData: ChatMessage) {
    const clientMessage: ClientChatMessage = {
      ...messageData,
      _clientId: uuidv4(), // Add unique client-side ID
    }
    messages.value.push(clientMessage)
    console.log(`${LOG_PREFIX} Added message with client ID ${clientMessage._clientId}`)
  }

  // --- Actions ---

  /**
   * Fetches the complete message history for initializing the chat.
   */
  async function fetchInitialMessages() {
    if (!sessionId.value) {
      console.log(`${LOG_PREFIX} fetchInitialMessages: No session ID found, skipping.`)
      isConnecting.value = false
      return
    }
    console.log(
      `${LOG_PREFIX} fetchInitialMessages: Fetching ALL messages for session ${sessionId.value}.`,
    )
    isConnecting.value = true
    error.value = null

    try {
      // Fetch ALL messages (no 'since' parameter)
      const response = await apiClient.getSessionMessagesApiChatSessionIdMessagesGet({
        sessionId: sessionId.value,
        // No 'since' parameter needed anymore
      })

      console.log(
        `${LOG_PREFIX} fetchInitialMessages: Received API response. Messages count: ${response.messages?.length ?? 0}`,
      )

      // Replace current messages with the full history
      messages.value = [] // Clear existing
      if (response.messages && response.messages.length > 0) {
        response.messages.forEach((msg) => {
          // Add each message with a client ID
          _addClientMessage(msg as ChatMessage)
        })
        console.log(
          `${LOG_PREFIX} fetchInitialMessages: Loaded ${messages.value.length} initial messages.`,
        )
      } else {
        console.log(
          `${LOG_PREFIX} fetchInitialMessages: No initial messages found or empty response.`,
        )
      }
      // No lastMessageId to update
    } catch (e) {
      console.error(`${LOG_PREFIX} fetchInitialMessages: Error during fetch.`)
      error.value = await _getErrorMessage(e, 'Failed to fetch initial messages.')
      if (error.value?.includes('Session not found')) {
        console.warn(
          `${LOG_PREFIX} fetchInitialMessages: Session not found on server, clearing local session.`,
        )
        clearSession()
      }
    } finally {
      console.log(`${LOG_PREFIX} fetchInitialMessages: Finished. isConnecting set to false.`)
      isConnecting.value = false
    }
  }

  /**
   * Sends a user message and adds the assistant's reply to the state.
   * @param userMessage The user message object (with client ID) added by the component.
   * @returns true on success, false on failure.
   */
  async function sendMessage(userMessage: ClientChatMessage): Promise<boolean> {
    // Extract text content for the API request
    const inputText = userMessage.textContent?.text
    if (!inputText) {
      console.error(`${LOG_PREFIX} sendMessage: Cannot send message, missing text content.`)
      error.value = 'Cannot send empty message.'
      return false
    }

    console.log(
      `${LOG_PREFIX} sendMessage: Attempting to send message for session ${sessionId.value || '(new session)'}: "${inputText.substring(0, 30)}..."`,
    )
    error.value = null
    isLoading.value = true
    let success = false
    const currentSessionId = sessionId.value

    const requestBody: ChatRequest = {
      sessionId: sessionId.value,
      content: inputText,
    }

    try {
      const response = await apiClient.handleChatApiChatPost({ chatRequest: requestBody })
      console.log(
        `${LOG_PREFIX} sendMessage: Received API response:`,
        JSON.stringify(response, null, 2),
      )

      if (!currentSessionId && response.sessionId) {
        sessionId.value = response.sessionId
        localStorage.setItem(SESSION_ID_STORAGE_KEY, response.sessionId)
        console.log(`${LOG_PREFIX} sendMessage: Started new session: ${response.sessionId}`)
        // If it's a new session, the user message needs its session ID updated
        const userMsgIndex = messages.value.findIndex((m) => m._clientId === userMessage._clientId)
        if (userMsgIndex !== -1) {
          messages.value[userMsgIndex].sessionId = response.sessionId
        }
      } else if (currentSessionId && response.sessionId !== currentSessionId) {
        // This case shouldn't happen with current backend logic but is a safeguard
        console.warn(
          `${LOG_PREFIX} sendMessage: Session ID changed unexpectedly from ${currentSessionId} to ${response.sessionId}`,
        )
        sessionId.value = response.sessionId // Update to the new ID
        localStorage.setItem(SESSION_ID_STORAGE_KEY, response.sessionId)
        // Update session ID for all existing messages? Or clear? For now, just update the user message.
        const userMsgIndex = messages.value.findIndex((m) => m._clientId === userMessage._clientId)
        if (userMsgIndex !== -1) {
          messages.value[userMsgIndex].sessionId = response.sessionId
        }
      }

      if (response.reply) {
        console.log(`${LOG_PREFIX} sendMessage: Received reply.`)
        // Add assistant reply with a client ID
        _addClientMessage(response.reply)
        console.log(`${LOG_PREFIX} sendMessage: Added assistant reply.`)
        success = true
      } else {
        console.error(`${LOG_PREFIX} sendMessage: API response did not contain a reply message.`)
        error.value = 'Received an empty reply from the server.'
        success = false
      }
    } catch (e) {
      console.error(`${LOG_PREFIX} sendMessage: Error during send.`)
      error.value = await _getErrorMessage(e, 'Failed to send message.')
      if (error.value?.includes('Session not found')) {
        console.warn(
          `${LOG_PREFIX} sendMessage: Session not found on server, clearing local session.`,
        )
        clearSession()
      }
      success = false
    } finally {
      console.log(
        `${LOG_PREFIX} sendMessage: Finished. isLoading set to false. Success: ${success}`,
      )
      isLoading.value = false
      return success
    }
  }

  /**
   * Clears the current session state and removes from local storage.
   */
  function clearSession() {
    console.log(`${LOG_PREFIX} clearSession: Clearing session state.`)
    const oldSessionId = sessionId.value
    sessionId.value = null
    localStorage.removeItem(SESSION_ID_STORAGE_KEY)
    messages.value = []
    // lastMessageId removed
    if (!error.value?.includes('Session not found')) {
      error.value = 'Session cleared or expired. Start a new chat by sending a message.'
    }
    isConnecting.value = false
    isLoading.value = false
    console.log(`${LOG_PREFIX} clearSession: Session ${oldSessionId} cleared.`)
  }

  /**
   * Initializes the chat state, fetching initial messages if a session exists.
   */
  async function initializeChat() {
    console.log(`${LOG_PREFIX} initializeChat: Initializing chat state...`)
    if (sessionId.value) {
      console.log(
        `${LOG_PREFIX} initializeChat: Found existing session ID ${sessionId.value}. Fetching history.`,
      )
      await fetchInitialMessages() // Fetch history once
    } else {
      console.log(`${LOG_PREFIX} initializeChat: No existing session found.`)
      isConnecting.value = false // Ensure connecting is false if no session
    }
    console.log(`${LOG_PREFIX} initializeChat: Initialization complete.`)
  }

  // --- Expose state and actions ---
  return {
    // State
    messages,
    sessionId,
    error,
    isLoading,
    isConnecting,
    // Getters
    hasSession,
    // Actions
    sendMessage,
    clearSession,
    initializeChat,
  }
})
