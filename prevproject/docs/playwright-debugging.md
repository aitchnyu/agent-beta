# Playwright Test Debugging Guide

## How to Modify a Test to Print Console Output

To debug a Playwright test by collecting browser console logs, add a console event handler to the page object in the test's `setUp` method or within the test method itself.

### Example Modification

**Original code:**
```python
def setUp(self) -> None:
    super().setUp()
    # ... create test data ...
    
    page = self.logged_in_page
    schema = ListPageSchema()
    page.goto(self.list_rows_url("BooleanFieldModel", schema))
    page.wait_for_selector("table")
```

**Modified code with console logging:**
```python
def setUp(self) -> None:
    super().setUp()
    # ... create test data ...
    
    page = self.logged_in_page
    schema = ListPageSchema()
    
    # Collect console logs for debugging
    def handle_console(msg: ConsoleMessage) -> None:
        print(
            {
                "type": msg.type,
                "text": msg.text,
                "location": msg.location,
            }
        )
        # Print each argument and evaluate its JSON value
        for arg in msg.args:
            try:
                print({"arg": arg, "json_value": arg.json_value()})
            except Exception as e:
                print({"arg": arg, "error": str(e)})
    
    page.on("console", handle_console)
    
    page.goto(self.list_rows_url("BooleanFieldModel", schema))
    page.wait_for_selector("table", timeout=2000)  # Optional: increase timeout
```

### Import Required

Ensure `ConsoleMessage` is imported from playwright:
```python
from playwright.sync_api import ConsoleMessage
```

Note: `ConsoleMessage` is already imported in `djangoapp/tests/test_playwright.py` at line 16.

## How to Run a Single Playwright Test

### Basic Command

```bash
cd frontend && npm run build && cd .. && uv run manage.py test djangoapp.tests.test_playwright.TestClassName.test_method_name --keepdb
```

### Examples

```bash
# Run a specific test method
cd frontend && npm run build && cd .. && uv run manage.py test djangoapp.tests.test_playwright.BooleanFilterE2ETestCase.test_boolean_filter_no_option --keepdb

# Run all tests in a test class
cd frontend && npm run build && cd .. && uv run manage.py test djangoapp.tests.test_playwright.BooleanFilterE2ETestCase --keepdb

# Run all Playwright tests
./run playwrighttest
```

### Command Breakdown

1. `cd frontend && npm run build && cd ..` - Build the frontend assets first
2. `uv run manage.py test` - Run Django tests using uv
3. `djangoapp.tests.test_playwright.TestClassName.test_method_name` - Full path to the test
4. `--keepdb` - Preserve the test database between runs (faster for repeated testing)

### Useful Flags

- `--keepdb` - Preserve test database (avoids recreation between runs)
- `--noinput` - Don't prompt for input (automatically destroy/recreate database)
- `-v 2` - Increase verbosity for more output

### Database Lock Issues

If you encounter "database is being accessed by other users" errors, you may need to:
1. Close other connections to the test database
2. Or use `--noinput` to force recreation (may fail if locked)

## Debugging Workflow

1. Identify the failing test from the full test run
2. Add console logging to the test's `setUp` or test method
3. Run the single test with `--keepdb` to see console output
4. Analyze the console output to identify the issue
5. Remove the debugging code after fixing the issue
