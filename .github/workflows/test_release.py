name: Tests

on: ["push", "pull_request"]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python: [2.7, 3.13]
    steps:

    - uses: actions/checkout@v2

    - name: Install python ${{ matrix.python }} with LisardByte/setup_python action
      if: matrix.python <= 2.7
      uses: LizardByte/actions/actions/setup_python@master
      with:
        python-version: ${{ matrix.python }}

    - name: Install python ${{ matrix.python }} with standard setup-python action
      if: matrix.python > 2.7
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
