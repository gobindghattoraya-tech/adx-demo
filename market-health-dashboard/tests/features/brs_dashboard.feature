Feature: ADX Good Book Certified™ — BRS Engine and API
  As an ADX Exchange Operator or Market Analyst
  I want a Good Book Certified™ dashboard with BRS scores
  So that I can identify order book health and drive market interventions

  Background:
    Given the BRS engine is available
    And sample order book rows exist for ticker "FAB" with tick size 0.01

  # ── Scenario 1: Dashboard HTTP response ─────────────────────────────────
  Scenario: Dashboard route returns HTTP 200
    Given the FastAPI test client is configured
    When I request GET "/dashboard"
    Then the response status code should be 200
    And the response content type should contain "text/html"
    And the response body should contain "Good Book Certified"

  # ── Scenario 2: BRS sub-scores are within valid range ───────────────────
  Scenario: BRS sub-scores are each between 0 and 100
    Given balanced order book rows for ticker "FAB"
    When I compute the BRS result
    Then the DC score should be between 0 and 100
    And the TF score should be between 0 and 100
    And the IR score should be between 0 and 100
    And the PLC score should be between 0 and 100
    And the BRS composite should be between 0 and 100

  # ── Scenario 3: BRS composite equals average of sub-scores ──────────────
  Scenario: BRS composite equals rounded average of DC TF IR PLC
    Given balanced order book rows for ticker "FAB"
    When I compute the BRS result
    Then the BRS composite should equal round of DC plus TF plus IR plus PLC divided by 4

  # ── Scenario 4: Gold certification requires BRS >= 80 ────────────────────
  Scenario: A symbol with high BRS receives the Gold tier
    Given order book rows that produce a high BRS for ticker "FAB"
    When I compute the BRS result
    Then the tier should be "Gold"

  # ── Scenario 5: Disqualified tier for very poor order books ───────────────
  Scenario: A symbol with very low BRS is Disqualified
    Given order book rows that produce a very low BRS for ticker "FAB"
    When I compute the BRS result
    Then the tier should be "Disqualified"

  # ── Scenario 6: Intraday generates 5 data points ─────────────────────────
  Scenario: Intraday simulation returns exactly 5 labelled BRS points
    Given a current BRS of 75 for ticker "FAB"
    When I generate the intraday snapshot
    Then the result should contain exactly 5 data points
    And the last point BRS should equal 75
    And every intraday BRS value should be between 0 and 100

  # ── Scenario 7: Intraday labels are correct ───────────────────────────────
  Scenario: Intraday labels follow the expected time series
    Given a current BRS of 80 for ticker "FAB"
    When I generate the intraday snapshot
    Then the labels should be T-4h T-3h T-2h T-1h Now

  # ── Scenario 8: Market summary API returns correct structure ──────────────
  Scenario: Market summary endpoint returns valid JSON structure
    Given the FastAPI test client is configured
    And the database contains mocked symbol and order book data
    When I request GET "/api/v1/market/summary"
    Then the response status code should be 200
    And the JSON body should contain key "total_symbols"
    And the JSON body should contain key "certified_count"
    And the JSON body should contain key "watchlist_count"
    And the JSON body should contain key "market_avg_brs"

  # ── Scenario 9: Symbols API returns list sorted by BRS desc ─────────────
  Scenario: Symbols list is ordered by BRS descending
    Given the FastAPI test client is configured
    And the database contains mocked symbol and order book data
    When I request GET "/api/v1/symbols"
    Then the response status code should be 200
    And the JSON body should be a list
    And the symbols should be ordered by BRS descending

  # ── Scenario 10: Symbol depth API returns BID and OFFER rows ─────────────
  Scenario: Depth endpoint returns BID and OFFER price levels
    Given the FastAPI test client is configured
    And the database contains mocked symbol and order book data
    When I request GET "/api/v1/symbols/FAB/depth"
    Then the response status code should be 200
    And the JSON body should be a list
    And the depth rows should include both BID and OFFER sides
