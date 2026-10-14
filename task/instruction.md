# Repair case-insensitive HTTP header lookup

The Requests checkout in /app has a deliberately seeded regression in
CaseInsensitiveDict. Repair it so that HTTP header lookup ignores casing,
without breaking updates, deletion, original-key casing, copying or equality.
Change source files, not tests. Dependencies are already installed; no network
access is required. This is a synthetic exercise, not an upstream Requests bug.
