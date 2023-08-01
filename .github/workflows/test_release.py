name: Tests

on: ["push", "pull_request"]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ['3.8', '3.9', '3.10', '3.11', '3.12-dev']
    steps:

    - uses: actions/checkout@v2

    - name: Set up Python ${{ matrix.python }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python }}

    - name: Install dependencies
      run: |
        pip install -U -r requirements_dev.txt
        pip install -U test_server

    - name: Run tests
      run: |
        make test
