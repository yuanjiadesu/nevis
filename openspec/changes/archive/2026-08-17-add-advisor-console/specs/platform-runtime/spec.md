## ADDED Requirements

### Requirement: Serve the console from the API

The system SHALL serve compiled console assets from the API origin in local and fictional-data UAT environments. The runtime image SHALL not require Node or a frontend service.

#### Scenario: Browser opens the platform

- **WHEN** a browser opens the platform origin
- **THEN** FastAPI returns the console, which calls API paths on the same origin

#### Scenario: Browser requests a static asset

- **WHEN** a browser requests a compiled asset
- **THEN** FastAPI returns it without intercepting health or protected routes

#### Scenario: API image is built

- **WHEN** the production image build completes
- **THEN** it contains compiled console assets and no Node runtime
