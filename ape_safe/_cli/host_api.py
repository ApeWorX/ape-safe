import os
from typing import Annotated

import click
import uvicorn
from ape import accounts
from ape.cli import ConnectedProviderCommand
from ape.types import AddressType
from eth_pydantic_types import Address
from fastapi import Depends, FastAPI, HTTPException

from ape_safe.accounts import SafeAccount
from ape_safe.client import MockSafeClient, SafeDetails

app = FastAPI()


def get_accounts() -> dict[AddressType, SafeAccount]:
    safe_account_container = accounts.containers["safe"]
    for safe in safe_account_container.accounts:
        safe.client = MockSafeClient(safe.contract)
    return {a.address: a for a in safe_account_container.accounts}


LocalSafeAccounts = Annotated[dict[AddressType, SafeAccount], Depends(get_accounts)]


# NOTE: Mimic official Safe API
@app.get("/api/v1/safes/{address}")
@app.get("/api/v1/safes/{address}/")
async def api_v1_get_safe_details(address: Address, safes: LocalSafeAccounts) -> SafeDetails:
    if not (safe := safes.get(address)):
        raise HTTPException(status_code=404, detail=f"Safe not found '{address}'.")

    return safe.client.safe_details


@click.command(cls=ConnectedProviderCommand)
@click.option("--port", type=int, default=8000)
def host(port):
    """Run a local-only Safe API for aggregating signatures"""
    os.environ["SAFE_TRANSACTION_SERVICE_URL"] = f"http://localhost:{port}"
    uvicorn.run(app)
