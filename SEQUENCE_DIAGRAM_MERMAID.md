# System Sequence Diagram (Mermaid)

## Complete Application Flow

```mermaid
sequenceDiagram
    title: Arbitrage Dashboard - Complete System Flow

    actor U as User
    participant RD as React Dashboard
    participant API as FastAPI Server
    participant SR as Service Runner
    participant MP as Market Poller
    participant SS as Similarity Service
    participant OP as Orderbook Poller
    participant AC as Arbitrage Calculator
    participant CM as Connection Manager
    participant DB as Supabase DB
    participant KA as Kalshi API
    participant PA as Polymarket API
    participant OA as OpenAI API

    rect rgb(240, 248, 255)
        Note over SR,CM: Phase 1: System Startup
        SR->>MP: spawn worker
        SR->>OP: spawn worker
        SR->>CM: initialize
    end

    rect rgb(255, 250, 240)
        Note over MP,PA: Phase 2: Market Discovery (every 5 minutes)
        MP->>KA: GET /markets
        activate KA
        KA-->>MP: 500 Kalshi markets
        deactivate KA

        MP->>PA: GET /markets
        activate PA
        PA-->>MP: 800 Polymarket markets
        deactivate PA

        MP->>DB: UPSERT 1300 markets
        DB-->>MP: OK
    end

    rect rgb(240, 255, 240)
        Note over MP,OA: Phase 3: Market Matching (per new market)
        loop For each new market
            MP->>SS: process_new_market(market)
            activate SS

            SS->>OA: POST /embeddings (market name + rules)
            activate OA
            OA-->>SS: [1536-dim vector]
            deactivate OA

            SS->>DB: Store embedding in pgvector
            SS->>DB: Search similar markets (cosine similarity)
            DB-->>SS: Candidates [{id, score}]

            alt score > 0.8 threshold
                SS->>OA: POST /chat/completions "Are these markets identical?"
                activate OA
                OA-->>SS: {is_identical: true, confidence: 0.95}
                deactivate OA

                alt LLM confirms match
                    SS->>DB: INSERT market_pair
                    DB-->>SS: pair_id
                end
            end

            deactivate SS
        end
    end

    rect rgb(255, 240, 245)
        Note over OP,CM: Phase 4: Arbitrage Detection (every 60 seconds)
        loop Every 60 seconds
            OP->>DB: SELECT all market_pairs
            DB-->>OP: 50 pairs

            loop For each pair
                OP->>KA: GET /orderbook/{market_id}
                KA-->>OP: {yes_bids, yes_asks, no_bids, no_asks}

                OP->>PA: GET /orderbook/{market_id}
                PA-->>OP: {yes_bids, yes_asks, no_bids, no_asks}

                OP->>DB: INSERT orderbook_snapshot
            end

            OP->>AC: Calculate arbitrage for all pairs
            activate AC

            Note over AC: profit = $1.00 - (yes + no) - fees

            alt profit > min_threshold
                AC->>DB: INSERT arbitrage_opportunity
            end

            deactivate AC
        end
    end

    rect rgb(245, 240, 255)
        Note over AC,RD: Phase 5: Real-Time Broadcast
        AC->>CM: broadcast(updated_data)
        activate CM

        CM->>DB: RPC: get_paired_markets_enriched()
        DB-->>CM: Complete enriched data

        CM-)RD: WebSocket push {type: "update", data: [...]}

        deactivate CM
    end

    rect rgb(255, 255, 240)
        Note over U,CM: Phase 6: User Interaction
        U->>RD: Open dashboard
        RD->>API: WebSocket connect ws://host/ws/market_pairs
        API->>CM: register connection
        CM-->>RD: Connected

        CM->>DB: get_paired_markets_enriched()
        DB-->>CM: Initial data
        CM-)RD: Initial data push

        RD->>U: Display market pairs with live arbitrage opportunities

        loop On each broadcast
            CM-)RD: Push update
            RD->>RD: Re-render UI
            RD->>U: Show updated prices (< 100ms latency)
        end
    end
```

## System Architecture Overview

```mermaid
flowchart TB
    subgraph External["External APIs"]
        KA[Kalshi Exchange API]
        PA[Polymarket Exchange API]
        OA[OpenAI API<br/>Embeddings + LLM]
    end

    subgraph Backend["Backend Services"]
        MP[Market Poller<br/>every 5 min]
        SS[Similarity Service<br/>Vector + LLM]
        OP[Orderbook Poller<br/>every 60s]
        AC[Arbitrage Calculator]
        CM[Connection Manager<br/>WebSocket]
    end

    subgraph API["API Layer"]
        FAPI[FastAPI Server]
        REST[REST Endpoints]
        WS[WebSocket Endpoint]
    end

    subgraph Database["Supabase Database"]
        TM[(markets<br/>1300 rows)]
        TP[(market_pairs<br/>50 rows)]
        TO[(orderbooks)]
        TAO[(arbitrage_opportunities)]
        TV[(pgvector embeddings)]
    end

    subgraph Frontend["Frontend"]
        RD[React Dashboard<br/>Next.js]
        MPC[Market Pair Cards]
        WSC[WebSocket Client]
    end

    U((User))

    KA --> MP
    PA --> MP
    KA --> OP
    PA --> OP
    OA --> SS

    MP --> TM
    MP --> SS
    SS --> TV
    SS --> TP
    OP --> TO
    OP --> AC
    AC --> TAO
    AC --> CM

    FAPI --> REST
    FAPI --> WS
    REST --> TM
    WS --> CM

    CM --> WSC
    WSC --> RD
    RD --> MPC
    MPC --> U
    U --> RD
```

## Data Flow Diagram

```mermaid
flowchart TD
    A[Kalshi & Polymarket<br/>Market Data] --> B[Fetch all markets<br/>every 5 min]
    B --> C[Transform to<br/>DatabaseMarket objects]
    C --> D[(Store in markets table<br/>1300+ records)]
    D --> E[Generate embeddings<br/>via OpenAI]
    E --> F[(Store in pgvector)]
    F --> G{Similarity > 0.8?}

    G -->|Yes| H[LLM Verification<br/>Are these identical?]
    G -->|No| I[No match found]

    H --> J{LLM confirms?}
    J -->|Yes| K[(Create market_pair)]
    J -->|No| L[Discard candidate]

    K --> M[Poll orderbooks<br/>every 60s]
    M --> N[(Store orderbook_snapshots)]
    N --> O[Calculate:<br/>profit = $1.00 - yes - no - fees]

    O --> P{Profit > threshold?}
    P -->|Yes| Q[(Store arbitrage_opportunity)]
    Q --> R[Broadcast to<br/>WebSocket clients]
    R --> S[Update React state]
    S --> T[Re-render UI]
    T --> U((See live arbitrage<br/>opportunity!))

    P -->|No| V[No profitable opportunity]
```

## Component Interactions Summary

| Phase | Components | Action | Frequency |
|-------|------------|--------|-----------|
| 1. Startup | ServiceRunner | Spawns all background workers | Once |
| 2. Market Discovery | MarketPoller → Exchanges → DB | Fetch & store markets | Every 5 min |
| 3. Market Matching | SimilarityService → OpenAI → DB | Embed, search, verify, pair | Per new market |
| 4. Arbitrage Detection | OrderbookPoller → Calculator → DB | Poll prices, calculate profit | Every 60s |
| 5. Broadcast | ConnectionManager → WebSocket | Push updates to all clients | After each calculation |
| 6. User Display | React Dashboard | Render live data | On each WS message |

## How to Render These Diagrams

1. **GitHub/GitLab**: Mermaid is natively supported - just view the markdown file

2. **VS Code**: Install "Markdown Preview Mermaid Support" extension

3. **Online Editor**: Use [mermaid.live](https://mermaid.live) to edit and export

4. **Export to PNG/SVG**: Use mermaid CLI:
   ```bash
   npm install -g @mermaid-js/mermaid-cli
   mmdc -i SEQUENCE_DIAGRAM_MERMAID.md -o diagram.png
   ```
