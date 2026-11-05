/** The skip for tests that need a path's permission bits to refuse access, as tests/fixtures/permissions.py's SKIP_AS_ROOT. */
import { test } from "bun:test"

// Root ignores permission bits, so no path refuses it.
export const skipAsRoot = test.skipIf(process.getuid?.() === 0)
