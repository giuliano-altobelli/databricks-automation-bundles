# Shared Libraries

Shared code is allowed only through explicit, tested packages.

Do not use broad cross-bundle Databricks `sync.paths` by default. A future shared package should own its own metadata, tests, and dependency lock.
