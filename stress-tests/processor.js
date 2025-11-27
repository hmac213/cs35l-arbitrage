/**
 * Artillery Custom Processor for Arbitrage Dashboard Stress Tests
 *
 * This module provides custom functions for advanced load testing scenarios:
 * - Tracking WebSocket message latency
 * - Validating market pairs data structure
 * - Custom metrics collection
 *
 * Usage in artillery.yml:
 *   config:
 *     processor: "./processor.js"
 */

'use strict';

// Track connection times for latency analysis
const connectionTimes = new Map();

// Track message counts per connection
const messageCounts = new Map();

/**
 * Before scenario hook - called before each virtual user starts
 */
function setupConnection(context, events, done) {
  // Generate unique connection ID
  context.vars.connectionId = `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  context.vars.connectionStartTime = Date.now();
  context.vars.messagesReceived = 0;

  return done();
}

/**
 * Track when WebSocket connection is established
 */
function onConnectionOpen(context, events, done) {
  const connectionTime = Date.now() - context.vars.connectionStartTime;

  // Emit custom metric for connection time
  events.emit('customStat', {
    stat: 'websocket.connection_time',
    value: connectionTime
  });

  console.log(`[${context.vars.connectionId}] Connected in ${connectionTime}ms`);

  return done();
}

/**
 * Process received WebSocket message
 * Validates the market pairs data structure and tracks metrics
 */
function processMarketPairsMessage(context, events, done) {
  const message = context.vars.wsResponse;
  context.vars.messagesReceived = (context.vars.messagesReceived || 0) + 1;

  try {
    const data = JSON.parse(message);

    // Track message size
    const messageSize = message.length;
    events.emit('customStat', {
      stat: 'websocket.message_size_bytes',
      value: messageSize
    });

    // Validate it's an array (expected format)
    if (Array.isArray(data)) {
      const pairCount = data.length;

      events.emit('customStat', {
        stat: 'market_pairs.count',
        value: pairCount
      });

      // Count opportunities
      const opportunityCount = data.filter(pair => pair.current_opportunity).length;
      events.emit('customStat', {
        stat: 'arbitrage_opportunities.active',
        value: opportunityCount
      });

      // Validate first pair structure (if exists)
      if (pairCount > 0) {
        const firstPair = data[0];
        const isValidStructure =
          firstPair.pair_id &&
          firstPair.market_1 &&
          firstPair.market_2 &&
          typeof firstPair.similarity_score === 'number';

        events.emit('customStat', {
          stat: 'market_pairs.valid_structure',
          value: isValidStructure ? 1 : 0
        });
      }

      console.log(`[${context.vars.connectionId}] Received ${pairCount} market pairs, ${opportunityCount} opportunities`);
    } else if (data.error) {
      // Handle error response
      console.error(`[${context.vars.connectionId}] Error: ${data.error}`);
      events.emit('customStat', {
        stat: 'websocket.errors',
        value: 1
      });
    } else if (message === 'pong') {
      // Ping/pong response
      events.emit('customStat', {
        stat: 'websocket.pong_received',
        value: 1
      });
    }
  } catch (e) {
    // Non-JSON message (like "pong")
    if (message !== 'pong') {
      console.error(`[${context.vars.connectionId}] Parse error: ${e.message}`);
    }
  }

  return done();
}

/**
 * Before request hook for REST API calls
 * Adds timing information
 */
function beforeRequest(requestParams, context, events, done) {
  context.vars.requestStartTime = Date.now();
  return done();
}

/**
 * After response hook for REST API calls
 * Validates response and tracks custom metrics
 */
function afterResponse(requestParams, response, context, events, done) {
  const responseTime = Date.now() - context.vars.requestStartTime;

  // Track response size
  const bodySize = response.body ? response.body.length : 0;
  events.emit('customStat', {
    stat: 'api.response_size_bytes',
    value: bodySize
  });

  // Parse and validate market pairs response
  if (requestParams.url === '/api/get_paired_markets' && response.statusCode === 200) {
    try {
      const data = JSON.parse(response.body);

      if (Array.isArray(data)) {
        events.emit('customStat', {
          stat: 'api.market_pairs_count',
          value: data.length
        });

        // Count active opportunities
        const activeOpps = data.filter(p => p.current_opportunity).length;
        events.emit('customStat', {
          stat: 'api.active_opportunities',
          value: activeOpps
        });
      }
    } catch (e) {
      console.error(`Failed to parse response: ${e.message}`);
    }
  }

  return done();
}

/**
 * Generate a realistic think time based on user behavior patterns
 * Returns a value between min and max with slight normal distribution
 */
function generateThinkTime(context, events, done) {
  const min = 2;
  const max = 10;

  // Box-Muller transform for normal distribution
  const u1 = Math.random();
  const u2 = Math.random();
  const normal = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);

  // Scale to our range with mean at center
  const mean = (min + max) / 2;
  const stdDev = (max - min) / 6; // 99.7% within range
  const thinkTime = Math.max(min, Math.min(max, mean + normal * stdDev));

  context.vars.thinkTime = Math.round(thinkTime * 1000); // Convert to ms

  return done();
}

/**
 * Log summary at end of scenario
 */
function logSummary(context, events, done) {
  const duration = (Date.now() - context.vars.connectionStartTime) / 1000;
  console.log(`[${context.vars.connectionId}] Session complete: ${context.vars.messagesReceived} messages in ${duration.toFixed(1)}s`);

  return done();
}

module.exports = {
  setupConnection,
  onConnectionOpen,
  processMarketPairsMessage,
  beforeRequest,
  afterResponse,
  generateThinkTime,
  logSummary
};
