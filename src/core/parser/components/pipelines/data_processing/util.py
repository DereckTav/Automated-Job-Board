def get_from(filters: dict, url_id: str, selectors: list[str], categories: list[str]) -> dict:
    general = filters.get('General', {})
    specific = filters.get('Specific', {}).get(url_id, {})

    processed = {}

    for cat in categories:
        cat_map = {}
        for s in selectors:
            # Combine General and Specific tags
            gen_tags = set(general.get(cat, {}).get(s, []))
            spec_tags = set(specific.get(cat, {}).get(s, []))

            # Deduplicate and normalize
            combined = {str(t).lower().strip() for t in (gen_tags | spec_tags)}

            if combined:
                cat_map[s] = combined

        if cat_map:
            processed[cat] = cat_map

    return processed
