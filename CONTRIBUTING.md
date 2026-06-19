
# Contributing

## Tests

Run the test suite:

```bash
pytest
```

## Style

Format and lint the code:

```bash
ruff format
ruff check --fix
```

## Documentation

Docs are built with [great-docs](https://posit-dev.github.io/great-docs/).

Build preview locally:

```bash
great-docs build && great-docs preview
```

Watch for changes and rebuild automatically:

```bash
great-docs build --watch
```

## All-contributors

Install the [All-contributors CLI tool](https://allcontributors.org/cli/installation/):

```bash
npm i -D all-contributors-cli
```

Add or amend contributors:

```
npx all-contributors
```
