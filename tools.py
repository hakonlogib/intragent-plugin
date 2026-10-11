"""MCP tool definitions — the plugin's tool surface.

One MCP tool per backend ``/tools/*`` endpoint, mirroring exactly the set the
Custom GPT sees (Regla, Tímavera, Unimaze — WooCommerce is a legacy demo and is
not exposed). Each tool is a thin wrapper: it declares the input schema and a
"when to use" description (which ChatGPT reads to decide when to call it), then
forwards to the backend via ``backend_client.call_tool``. Field defaults and
bounds are copied from the backend request models so the two channels accept
identical input.

Safety annotations mirror the backend's consequential flag: everything is
``readOnlyHint`` except ``unimaze_mark_as_imported``, which mutates state and is
marked destructive so ChatGPT confirms before calling.
"""
from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from backend_client import call_tool


def _read(title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, readOnlyHint=True, openWorldHint=True)


def _write(title: str) -> ToolAnnotations:
    return ToolAnnotations(
        title=title, readOnlyHint=False, destructiveHint=True, openWorldHint=True
    )


def register_tools(mcp: MCPServer) -> None:
    """Register every tool on the given MCPServer instance."""

    # -- Regla: accounting (ReglaRestApi) -----------------------------------
    @mcp.tool(annotations=_read("List Regla sales invoices"))
    async def regla_list_invoices(
        start_date: Annotated[str, Field(description="Start of period, ISO date e.g. 2026-01-01. Empty = start of current year.")] = "",
        end_date: Annotated[str, Field(description="End of period, ISO date. Empty = today.")] = "",
        limit: Annotated[int, Field(ge=1, le=100, description="Max invoices to return.")] = 20,
    ):
        """List sales invoices (reikningar) from Regla for a period. Use for
        questions about invoices, recent billing, or accounts receivable. Regla
        has no explicit paid/unpaid flag and pay_date can be a future planned
        date, so do not infer payment from it alone."""
        return await call_tool("regla", "list_invoices", {"start_date": start_date, "end_date": end_date, "limit": limit})

    @mcp.tool(annotations=_read("Get one Regla invoice by number"))
    async def regla_get_invoice(
        invoice_number: Annotated[str, Field(description="Regla invoice number to look up.")],
        start_date: Annotated[str, Field(description="Start of search period, ISO date. Empty = start of current year.")] = "",
        end_date: Annotated[str, Field(description="End of search period, ISO date. Empty = today.")] = "",
    ):
        """Fetch full details of a single Regla sales invoice by number,
        including line items and totals. Prefer this over listing when an
        invoice number is known."""
        return await call_tool("regla", "get_invoice", {"invoice_number": invoice_number, "start_date": start_date, "end_date": end_date})

    @mcp.tool(annotations=_read("List or search Regla customers"))
    async def regla_list_customers(
        query: Annotated[str, Field(description="Free-text search (name or kennitala). Empty lists all.")] = "",
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ):
        """List or search customers (viðskiptavinir) in Regla. Use to look
        someone up by name or kennitala, or to list who the company does
        business with."""
        return await call_tool("regla", "list_customers", {"query": query, "limit": limit})

    @mcp.tool(annotations=_read("Regla account balances at a date"))
    async def regla_account_balance(
        start_date: Annotated[str, Field(description="Start of period, ISO date. Empty = start of current year.")] = "",
        end_date: Annotated[str, Field(description="Balance as-of date, ISO date. Empty = today.")] = "",
        limit: Annotated[int, Field(ge=1, le=500)] = 100,
    ):
        """Get account balances at a date from Regla (staða bókhaldslykla). Use
        for the company's financial position: per-account balances over a
        period, saldo, or debit/credit totals."""
        return await call_tool("regla", "account_balance", {"start_date": start_date, "end_date": end_date, "limit": limit})

    @mcp.tool(annotations=_read("List or search Regla products"))
    async def regla_list_products(
        query: Annotated[str, Field(description="Free-text search (name or product number). Empty lists all.")] = "",
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ):
        """List or search products (vörur) in the Regla catalogue. Use to look
        up a product by name or number, or to get prices, stock levels, or VAT
        rates."""
        return await call_tool("regla", "list_products", {"query": query, "limit": limit})

    @mcp.tool(annotations=_read("List Regla ledger transactions"))
    async def regla_list_transactions(
        start_date: Annotated[str, Field(description="Start of period, ISO date. Empty = no lower bound.")] = "",
        end_date: Annotated[str, Field(description="End of period, ISO date. Empty = no upper bound.")] = "",
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ):
        """List accounting transactions (færslur/hreyfingar) from the Regla
        ledger. Use for individual bookkeeping entries or debits/credits in a
        period. For account totals use regla_account_balance instead."""
        return await call_tool("regla", "list_transactions", {"start_date": start_date, "end_date": end_date, "limit": limit})

    @mcp.tool(annotations=_read("Search Regla chart of accounts"))
    async def regla_list_account_keys(
        query: Annotated[str, Field(description="Free-text search (account number or name). Empty lists all.")] = "",
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ):
        """Search the Regla chart of accounts (bókhaldslyklar). Use to find
        which accounts exist or to look up an account by number or name."""
        return await call_tool("regla", "list_account_keys", {"query": query, "limit": limit})

    # -- Regla: verkbókhald (ReglaWebService) -------------------------------
    @mcp.tool(annotations=_read("List Regla projects (verk)"))
    async def regla_list_projects(
        query: Annotated[str, Field(description="Free-text filter on project name, description or customer. Empty lists all.")] = "",
        limit: Annotated[int, Field(ge=1, le=200)] = 25,
    ):
        """List projects from Regla's project accounting (verkbókhald). Use to
        find what jobs exist, which customer a job belongs to, or to look up a
        project id before asking about its hours. This is the billing view of
        jobs — not the same as the Tímavera project list."""
        return await call_tool("regla", "list_projects", {"query": query, "limit": limit})

    @mcp.tool(annotations=_read("Get one Regla project in detail"))
    async def regla_get_project(
        project_id: Annotated[int, Field(description="Regla project id, from regla_list_projects.")],
    ):
        """Get a single project with all its hour entries and materials. Use for
        questions about one specific job: total hours, who worked on it, what has
        been invoiced. Get the project id from regla_list_projects first."""
        return await call_tool("regla", "get_project", {"project_id": project_id})

    @mcp.tool(annotations=_read("List hours logged against Regla projects"))
    async def regla_list_job_hours(
        start_date: Annotated[str, Field(description="ISO date, e.g. 2026-01-01. Empty = 90 days ago.")] = "",
        end_date: Annotated[str, Field(description="ISO date. Empty = today.")] = "",
        unbilled_only: Annotated[bool, Field(description="Only entries not yet charged to an invoice.")] = False,
        employee: Annotated[str, Field(description="Optional employee name or username to filter by.")] = "",
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ):
        """List project hour entries (verkbókhaldsfærslur) for a period. Use for
        how many hours went on jobs, and especially for which work has not been
        invoiced yet ("hvaða tímar eru óreikningsfærðir?"). This is the billing
        view of hours; use timavera_list_time_entries for the operational view."""
        return await call_tool("regla", "list_job_hours", {"start_date": start_date, "end_date": end_date, "unbilled_only": unbilled_only, "employee": employee, "limit": limit})

    # -- Tímavera: time tracking --------------------------------------------
    @mcp.tool(annotations=_read("List Tímavera time entries"))
    async def timavera_list_time_entries(
        employee: Annotated[str, Field(description="Optional employee name filter. Empty returns everyone.")] = "",
        days: Annotated[int, Field(ge=1, le=90, description="Look back this many days.")] = 7,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ):
        """List recent time entries (tímaskráningar) from Tímavera. Use for who
        logged time, hours worked on a project, or a person's recent timesheet.
        Durations are in seconds."""
        return await call_tool("timavera", "list_time_entries", {"employee": employee, "days": days, "limit": limit})

    @mcp.tool(annotations=_read("Summarise Tímavera hours"))
    async def timavera_time_summary(
        period: Annotated[Literal["week", "month"], Field(description="Reporting window.")] = "week",
    ):
        """Summarise logged hours per employee and per project from Tímavera.
        Use for roll-ups and utilisation overviews. Durations are in seconds."""
        return await call_tool("timavera", "time_summary", {"period": period})

    @mcp.tool(annotations=_read("List Tímavera employees"))
    async def timavera_list_employees():
        """List the company's employees (starfsmenn) from Tímavera. Use to get
        the staff roster or an employee's id to filter other queries."""
        return await call_tool("timavera", "list_employees", {})

    @mcp.tool(annotations=_read("List Tímavera projects"))
    async def timavera_list_projects():
        """List the company's projects (verkefni) from Tímavera. Parent (folder)
        projects list their sub-projects under children. Use to see ongoing work
        or get a project's id."""
        return await call_tool("timavera", "list_projects", {})

    @mcp.tool(annotations=_read("Get GPS points for a work log"))
    async def timavera_get_work_log_locations(
        work_log_id: Annotated[int, Field(description="Id of the work log (time entry) to fetch GPS locations for.")],
    ):
        """Get the GPS locations recorded for a single Tímavera work log. Use to
        verify where a time entry was logged. Find work_log_id via
        timavera_list_time_entries first."""
        return await call_tool("timavera", "get_work_log_locations", {"work_log_id": work_log_id})

    @mcp.tool(annotations=_read("Tímavera billing status"))
    async def timavera_billing_status():
        """Get the company's Tímavera billing/subscription status."""
        return await call_tool("timavera", "billing_status", {})

    # -- Unimaze: e-invoicing -----------------------------------------------
    @mcp.tool(annotations=_read("List pending incoming invoices from Unimaze"))
    async def unimaze_list_pending_invoices(
        transaction_group: Annotated[str | None, Field(description="Filter by type: SubmitInvoice, CorrectWithCredit, SubmitOrder. Omit for all.")] = None,
        limit: Annotated[int, Field(ge=1, le=10000, description="Max documents to return.")] = 50,
        offset: Annotated[int, Field(ge=0, description="Items to skip (multiple of limit).")] = 0,
    ):
        """List incoming invoices (innkomnir reikningar) waiting to be processed
        in the Unimaze e-invoicing system. Use for received bills, pending
        invoices from suppliers, or what documents have arrived."""
        return await call_tool("unimaze", "list_pending_invoices", {"transaction_group": transaction_group, "limit": limit, "offset": offset})

    @mcp.tool(annotations=_read("Get full invoice details from Unimaze"))
    async def unimaze_get_invoice(
        message_id: Annotated[str, Field(description="The message GUID from the pending list.")],
    ):
        """Fetch the full details of a specific invoice — amounts, line items,
        VAT, due date, supplier and customer info. The message_id comes from
        unimaze_list_pending_invoices."""
        return await call_tool("unimaze", "get_invoice", {"message_id": message_id})

    @mcp.tool(annotations=_write("Mark an Unimaze invoice as imported"))
    async def unimaze_mark_as_imported(
        message_id: Annotated[str, Field(description="The message GUID to mark as imported.")],
    ):
        """Mark an invoice as imported/processed so it no longer appears in the
        pending list. Use when the user confirms they are done with an invoice.
        This is a write operation — confirm with the user first."""
        return await call_tool("unimaze", "mark_as_imported", {"message_id": message_id})
