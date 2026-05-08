Feature: Market Health Dashboard — 3-Tier Application

  Background:
    Given the Market Health Dashboard service is running

  Scenario: Frontend page loads successfully
    When a user navigates to the frontend URL "/"
    Then the HTTP response status code is 200
    And the page contains "Market Health Dashboard"
    And the page contains "ADX"

  Scenario: Hello World is retrieved from the database and displayed
    Given the database contains a row with value "Hello World"
    When a user navigates to the frontend URL "/"
    Then the HTTP response status code is 200
    And the page displays the text "Hello World"

  Scenario: Health endpoint responds correctly
    When a GET request is made to "/health"
    Then the HTTP response status code is 200
    And the response JSON field "status" equals "ok"

  Scenario: Hello endpoint returns database value
    Given the database contains a row with value "Hello World"
    When a GET request is made to "/hello"
    Then the HTTP response status code is 200
    And the response JSON field "message" equals "Hello World"

  Scenario: ADX branding is correctly applied
    When a user navigates to the frontend URL "/"
    Then the page header contains the ADX brand name
    And the page contains "Market Health Dashboard"

  Scenario: Application handles database unavailability gracefully
    Given the database is unavailable
    When a GET request is made to "/hello"
    Then the HTTP response status code is 503
    And the response contains a meaningful error message

  Scenario: README contains deployment URLs
    When a developer reads the README.md file
    Then the README contains "Frontend URL"
    And the README contains "Backend URL"
