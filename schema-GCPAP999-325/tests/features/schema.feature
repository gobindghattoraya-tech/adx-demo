Feature: Stock Exchange Core Database Schema — adx_exchange

  Background:
    Given the "adx_exchange" database is reachable
    And all migration scripts have been applied

  # ── Table structure ────────────────────────────────────────────────────────

  Scenario: All 5 core tables exist with correct names
    When I query the information_schema for public table names
    Then the following tables should exist:
      | table_name  |
      | sectors     |
      | symbols     |
      | order_books |
      | trades      |
      | watchlists  |

  # ── ENUM types ────────────────────────────────────────────────────────────

  Scenario: ENUM type order_side contains BID and OFFER
    When I query pg_type for enum "order_side"
    Then the enum values should include "BID" and "OFFER"

  Scenario: ENUM type order_status_type contains all status values
    When I query pg_type for enum "order_status_type"
    Then the enum values should include "OPEN", "PARTIAL", "FILLED", and "CANCELLED"

  # ── Symbol–Sector FK ──────────────────────────────────────────────────────

  Scenario: A symbol is linked to a sector via FK
    Given a sector "Technology" is inserted
    When I insert symbol "AAPL" with tick_size 0.01 linked to that sector
    Then the symbol insert should succeed
    And a join of symbols and sectors should return sector_name "Technology" for "AAPL"

  Scenario: Inserting a symbol with a non-existent sector_id is rejected
    When I insert a symbol with a sector_id of 99999 that does not exist
    Then the insert should fail with a constraint error

  # ── Tick size validation ─────────────────────────────────────────────────

  Scenario: An order with an invalid tick price is rejected
    Given a sector "Commodities" is inserted
    And symbol "XAUUSD" exists with tick_size 0.50
    When I insert an order for "XAUUSD" with price 2000.25
    Then the order insert should fail with a tick validation error

  Scenario: An order with a valid tick price is accepted
    Given a sector "Commodities" is inserted
    And symbol "XAUUSD" exists with tick_size 0.50
    When I insert an order for "XAUUSD" with price 2000.50
    Then the order insert should succeed

  # ── Trade integrity ───────────────────────────────────────────────────────

  Scenario: A trade with incorrect total_value is rejected
    Given a sector "Technology" is inserted
    And symbol "AAPL" exists with tick_size 0.01
    And a BUY order and a SELL order exist for "AAPL" at price 150.00
    When I insert a trade with execution_price 150.00, quantity 10, total_value 999.00
    Then the trade insert should fail with a check constraint error

  Scenario: A valid trade is recorded successfully
    Given a sector "Technology" is inserted
    And symbol "AAPL" exists with tick_size 0.01
    And a BUY order and a SELL order exist for "AAPL" at price 150.00
    When I insert a trade with execution_price 150.00, quantity 10, total_value 1500.00
    Then the trade insert should succeed

  # ── Watchlist UUID + uniqueness ───────────────────────────────────────────

  Scenario: A watchlist entry uses a UUID primary key
    Given a sector "Technology" is inserted
    And symbol "AAPL" exists with tick_size 0.01
    When I insert a watchlist entry for user_id 1 watching "AAPL"
    Then the watchlist insert should succeed
    And the watchlist_id returned should be a valid UUID

  Scenario: A duplicate watchlist entry is rejected
    Given a sector "Technology" is inserted
    And symbol "AAPL" exists with tick_size 0.01
    And a watchlist entry for user_id 1 watching "AAPL" already exists
    When I insert another watchlist entry for user_id 1 watching "AAPL"
    Then the watchlist insert should fail with a unique constraint error

  # ── Indexes ───────────────────────────────────────────────────────────────

  Scenario: All required performance indexes exist
    When I query pg_indexes for schema "public"
    Then the following indexes should be present:
      | tablename   | indexname                  |
      | order_books | idx_order_books_symbol_id  |
      | order_books | idx_order_books_status     |
      | order_books | idx_order_books_sym_open   |
      | trades      | idx_trades_symbol_id       |
      | watchlists  | idx_watchlists_user_id     |
      | watchlists  | idx_watchlists_symbol_id   |
