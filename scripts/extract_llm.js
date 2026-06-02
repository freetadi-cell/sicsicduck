#!/usr/bin/env node
/**
 * LLM extraction helper for update_rates.py
 * Calls the OpenClaw agent runtime to process a prompt and return JSON.
 * 
 * Usage: node extract_llm.js "<prompt>"
 * Output: JSON object on stdout, or "null" on failure
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const prompt = process.argv[2];
if (!prompt) {
  console.error('Usage: node extract_llm.js "<prompt>"');
  process.exit(1);
}

// Write prompt to temp file
const tmpFile = path.join('/tmp', `llm_prompt_${Date.now()}.txt`);
fs.writeFileSync(tmpFile, prompt);

try {
  // Use openclaw tui with message and timeout
  const result = execSync(
    `openclaw tui --local --message "$(cat ${tmpFile})" --timeout-ms 60000 2>/dev/null`,
    {
      timeout: 65000,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }
  );
  console.log(result.trim());
} catch (e) {
  // Try alternative: use gateway WebSocket
  try {
    const { execFileSync } = require('child_process');
    // Just run as a simple eval
    const ws = require('ws');
    
    // Connect to local gateway
    const GW_URL = 'ws://127.0.0.1:18789';
    
    const gateway = new ws(GW_URL);
    
    gateway.on('open', () => {
      // Send chat message
      gateway.send(JSON.stringify({
        type: 'chat',
        message: prompt,
        model: 'glm-5-turbo',
      }));
      
      setTimeout(() => {
        gateway.close();
        process.exit(1);
      }, 30000);
    });
    
    let fullResponse = '';
    gateway.on('message', (data) => {
      try {
        const msg = JSON.parse(data);
        if (msg.type === 'assistant' || msg.type === 'reply') {
          const text = msg.text || msg.content || '';
          fullResponse += text;
          // Check if we got a complete response
          if (msg.done || msg.complete) {
            console.log(fullResponse.trim());
            gateway.close();
            process.exit(0);
          }
        }
      } catch (e) {
        // Ignore non-JSON messages
      }
    });
    
  } catch (e2) {
    console.error('null');
    process.exit(1);
  }
} finally {
  try { fs.unlinkSync(tmpFile); } catch (e) {}
}
