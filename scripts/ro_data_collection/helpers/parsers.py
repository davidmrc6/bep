def parse_repo_item(item: dict, query: str) -> dict:
    """Extract a flat record from a repository search result item."""
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
        "pushed_at": item.get("pushed_at"),
        "default_branch": item.get("default_branch"),
        "license": (item.get("license") or {}).get("spdx_id"),
        "topics": ",".join(item.get("topics", [])),
        "is_fork": item.get("fork"),
        "size_kb": item.get("size"),
        "owner_login": (item.get("owner") or {}).get("login"),
        "owner_type": (item.get("owner") or {}).get("type"),
        "source": "repo_search",
        "matched_query": query,
    }


def parse_code_item(item: dict, query: str) -> dict:
    """Extract a flat record from a code search result item."""
    repo = item.get("repository", {})
    return {
        "repo_full_name": repo.get("full_name"),
        "repo_url": repo.get("html_url"),
        "description": repo.get("description"),
        "language": item.get("language"),  # file-level language if present
        "file_name": item.get("name"),
        "file_path": item.get("path"),
        "file_url": item.get("html_url"),
        "owner_login": (repo.get("owner") or {}).get("login"),
        "owner_type": (repo.get("owner") or {}).get("type"),
        "is_fork": repo.get("fork"),
        "source": "code_search",
        "matched_query": query,
    }