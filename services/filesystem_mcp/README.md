# filesystem-mcp

Filesystem MCP server. The command defaults to stdio; `--transport http` exposes `/mcp` and `/healthz`.

It ports the tool surface of `/Users/cofob/Development/mcp-filesystem-server`
to Python and restricts all reads and writes to one configured root directory.
