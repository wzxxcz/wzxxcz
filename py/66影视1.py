        content = ""
        # 优先取 detail-content（完整简介）
        m = re.search(
            r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</span>',
            html, re.I
        )
        if m:
            content = self._clean(m.group(1))

        # 再取 detail-sketch（被截断的短简介）
        if not content:
            m = re.search(
                r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>',
                html, re.I
            )
            if m:
                content = self._clean(m.group(1))

        # 最后兜底 meta description
        if not content:
            m = re.search(
                r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                html, re.I
            )
            if m:
                content = self._clean(m.group(1))

        # 统一加前缀
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX
