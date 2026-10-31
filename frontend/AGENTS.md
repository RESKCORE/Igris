<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

- Keep sample workspace records in a shared browser-safe demo module and consume them through the existing mock API so dashboard and detail pages agree.
- Workspace content uses leaf-route metadata and shared presentation helpers; profile changes are session-only demo interactions, not real account or permission changes.
- Dashboard analytics derive from the existing mock API records through browser-safe aggregation helpers; chart components use shadcn ChartContainer and Recharts so totals stay consistent with detail pages.
- Page entrance motion uses Framer Motion in the shared AppShell, keyed by pathname with reduced-motion guards; the dashboard keeps its own staggered entrance without a duplicate shell animation. Shadow effects use semantic CSS theme tokens to preserve the Igris palette.
- Exceptions use browser-safe detail formatting and filtering helpers with a dedicated presentation card; keep resolution actions on the existing mock API so all workspace views stay consistent.
