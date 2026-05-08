Feature: ADX Symbol and Order Book Data Population
  As a Market Health Dashboard developer
  I want the ADX seed script to populate sectors, symbols and order books
  So that the dashboard has realistic exchange data for display and validation

  Background:
    Given a mock asyncpg connection is available
    And the seed data constants are loaded

  Scenario: Sectors are seeded with correct names
    When the seed_sectors function is called
    Then 6 rows are upserted for sectors
    And the returned sector map contains "Banking"
    And the returned sector map contains "Energy"
    And the returned sector map contains "Real Estate"

  Scenario: All 15 symbols are seeded
    When the seed_symbols function is called with a valid sector map
    Then 15 symbols are processed
    And the symbol "FAB" is in the returned symbol map
    And the symbol "IHC" is in the returned symbol map
    And the symbol "BOROUGE" is in the returned symbol map

  Scenario: Order book generator produces correct number of orders
    Given the tick_size is 0.01 and mid_price is 15.20
    When generate_orders is called with num_levels=10
    Then the result contains 10 BID orders
    And the result contains 10 OFFER orders
    And all BID prices are below 15.20
    And all OFFER prices are above 15.20

  Scenario: All generated prices respect tick_size
    Given the tick_size is 0.05 and mid_price is 22.80
    When generate_orders is called with num_levels=10
    Then every price in the result is a multiple of 0.05

  Scenario: Order book generator is deterministic with a fixed seed
    Given the tick_size is 0.01 and mid_price is 9.80
    When generate_orders is called twice with the same seed=42
    Then both results are identical

  Scenario: Seed script skips order books already populated
    Given the order_books table already has 20 rows for symbol_id 1
    When seed_order_books is called for that symbol
    Then no additional INSERT is executed for symbol_id 1

  Scenario: Seed script fails gracefully on missing DB_PASSWORD
    Given the DB_PASSWORD environment variable is not set
    When run_seed is called
    Then a KeyError is raised
    And the process would exit with code 1
