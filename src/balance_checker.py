import asyncio
from prettytable import PrettyTable
from .utils import load_seeds, create_wallet_from_seed, get_wallet_balance


async def check_wallet_balances() -> None:
    """Check balances of all wallets from wallets.txt"""
    seeds = await load_seeds()
    
    if not seeds:
        print("No seeds found in wallets.txt")
        return
    
    # Create PrettyTable with required columns
    table = PrettyTable()
    table.field_names = ["#", "Address (v4r2)", "Balance (TON)", "Status"]
    table.align["#"] = "r"
    table.align["Address (v4r2)"] = "l"
    table.align["Balance (TON)"] = "r"
    table.align["Status"] = "c"
    
    print(f"Checking {len(seeds)} wallets...")
    
    # Process wallets concurrently for better performance
    tasks = []
    for i, seed in enumerate(seeds, 1):
        tasks.append(_check_single_wallet(i, seed))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Add results to table
    for result in results:
        if isinstance(result, Exception):
            table.add_row([
                "?",
                "Error processing wallet",
                "Error", 
                f"Error: {str(result)[:20]}..."
            ])
        else:
            table.add_row(result)
    
    print("\nWallet Balances:")
    print(table)


async def _check_single_wallet(wallet_num: int, seed: str) -> tuple:
    """Check balance for a single wallet"""
    try:
        # Create wallet from seed
        address, wallet = await create_wallet_from_seed(seed)
        
        # Get balance
        balance_info = await get_wallet_balance(address)
        
        if balance_info["success"]:
            balance_ton = balance_info["balance_ton"]
            status = balance_info["status"]
            
            # Format status for display
            status_display = "✅ Active" if status == "active" else "❌ Inactive"
            
            return (
                wallet_num,
                address,
                f"{balance_ton:.4f}",
                status_display
            )
        else:
            return (
                wallet_num,
                address,
                "Error",
                balance_info["error"]
            )
            
    except Exception as e:
        return (
            wallet_num,
            "Error generating wallet",
            "Error",
            f"Error: {str(e)[:20]}..."
        )
