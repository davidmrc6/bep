def parse_repo_item(item: dict, query: str) -> dict:
    """Extract key fields from a repository search result item."""
    return {
        "repo_full_name": item.get("full_name"),
        "repo_url": item.get("html_url"),
        "description": item.get("description"),
        "language": item.get("language"),
        "stargazers_count": item.get("stargazers_count"),
        "forks_count": item.get("forks_count"),
        "open_issues_count": item.get("open_issues_count"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "license": (item.get("license") or {}).get("spdx_id"),
        "topics": ",".join(item.get("topics", [])),
        "is_fork": item.get("fork"),
        "size_kb": item.get("size"),
        "owner_login": (item.get("owner") or {}).get("login"),
        "owner_type": (item.get("owner") or {}).get("type"),
        "matched_query": query,
    }