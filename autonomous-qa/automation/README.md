# automation/

This directory is a placeholder for **standalone, hand-authored**
Playwright/Selenium scripts that fall outside the platform's normal
AI-generation-and-healing pipeline - for example, a fixed smoke-test
script a team wants to run identically in every environment without any
AI involvement at all.

The platform's actual Playwright and Selenium execution engines live in
`backend/app/services/execution/` (`playwright_engine.py`,
`selenium_engine.py`) and operate on `TestCase`/`TestStep` rows produced
by discovery + AI generation, not on files in this directory. Nothing in
the running system currently reads from `automation/playwright/` or
`automation/selenium/` - they are reserved for teams who want to check
in supplementary, engine-specific scripts alongside the generated test
suite.
