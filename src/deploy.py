import asyncio
import random
from typing import Dict, Any
from .utils import (
    load_seeds, create_wallet_from_seed, get_wallet_balance,
    get_wallet_seqno, send_transaction_boc, create_transfer_transaction,
    generate_random_address, await_seqno_increment
)


async def _activate_single_wallet(wallet_info: Dict[str, Any]) -> Dict[str, Any]:
    """Handles the activation logic for a single wallet."""
    try:
        print(f"\nProcessing activation for wallet #{wallet_info['index']}: {wallet_info['address']}")

        balance_info = await get_wallet_balance(wallet_info['address'])
        if not balance_info["success"] or balance_info["balance_ton"] < 0.001:
            error_msg = f"Insufficient balance for activation (balance: {balance_info.get('balance_ton', 0):.6f} TON). Needs ~0.001 TON."
            print(f"  ❌ {error_msg}")
            return {"success": False, "error": error_msg}

        print(f"  🔄 Activating wallet by sending dust transaction...")
        
        max_retries = 3
        last_error = "Unknown error"

        for attempt in range(max_retries):
            try:
                seqno_result = await get_wallet_seqno(wallet_info["address"])
                if not seqno_result["success"]:
                    last_error = f"Failed to get seqno: {seqno_result.get('error', 'N/A')}"
                    await asyncio.sleep(1)
                    continue
                
                seqno = seqno_result["seqno"]
                if seqno > 0:
                    print("  ✅ Wallet is already active (seqno > 0).")
                    return {"success": True, "activated": False, "message": "Already active"}

                random_address = await generate_random_address()
                dust_amount = random.uniform(0.000000001, 0.00000001)

                boc = await create_transfer_transaction(
                    wallet_info["wallet"], random_address, dust_amount, seqno
                )
                
                send_result = await send_transaction_boc(boc)
                
                if send_result["success"]:
                    print(f"  ✅ Activation transaction sent! Waiting for confirmation...")
                    print(f"  💳 Transaction: {send_result.get('explorer_link', 'N/A')}")

                    confirmed = await await_seqno_increment(wallet_info["address"], seqno)
                    if confirmed:
                        print("  🎉 Wallet successfully activated!")
                        return {"success": True, "activated": True}
                    else:
                        last_error = "Confirmation timeout"
                        print("  ❌ Activation sent but confirmation timed out.")
                    
                    break
                else:
                    last_error = send_result.get('error', 'Unknown send error')
                    print(f"  Attempt {attempt + 1}/{max_retries} failed: {last_error}")

            except Exception as tx_error:
                last_error = f"Exception during activation attempt: {str(tx_error)}"
                print(f"  Attempt {attempt + 1}/{max_retries} failed with exception: {last_error}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2)

        print(f"  ❌ Activation failed for {wallet_info['address']} after {max_retries} attempts: {last_error}")
        return {"success": False, "error": last_error}

    except Exception as e:
        error_msg = f"Activation failed with an unexpected error: {str(e)}"
        print(f"  ❌ {error_msg}")
        return {"success": False, "error": error_msg}


async def deploy_wallet() -> None:
    """Deploy wallets by sending small amounts to activate them"""
    seeds = await load_seeds()
    
    if not seeds:
        print("No seeds found in wallets.txt")
        return
        
    if len(seeds) < 2:
        print("Need at least 2 wallets for deployment (first as funding wallet)")
        return
    
    main_seed = seeds[0]
    main_address, _ = await create_wallet_from_seed(main_seed)
    
    print(f"Funding wallet address: {main_address}")
    
    main_balance_info = await get_wallet_balance(main_address)
    if not main_balance_info["success"]:
        print(f"Error getting funding wallet balance: {main_balance_info['error']}")
        return
    
    main_balance = main_balance_info["balance_ton"]
    print(f"Funding wallet balance: {main_balance:.4f} TON")
    
    if main_balance_info["status"] != "active":
        print("Funding wallet is not active! Cannot deploy other wallets.")
        return
    
    wallets_to_deploy = []
    
    print(f"\nChecking wallets to deploy ({len(seeds) - 1} wallets):")
    
    for i, seed in enumerate(seeds[1:], 1):
        address, wallet = await create_wallet_from_seed(seed)
        
        balance_info = await get_wallet_balance(address)
        if balance_info["success"]:
            status = balance_info["status"]
            balance = balance_info["balance_ton"]
            
            if status == "active":
                print(f"Wallet #{i}: {address}")
                print(f"  → Already active (balance: {balance:.6f} TON)")
            elif balance > 0:
                 wallets_to_deploy.append({
                    "wallet": wallet,
                    "address": address,
                    "index": i
                })
                 print(f"Wallet #{i}: {address}")
                 print(f"  → Needs deployment (status: {status}, balance: {balance:.6f} TON)")
            else:
                print(f"Wallet #{i}: {address}")
                print(f"  → Needs deployment but has 0 TON. Please fund first.")
        else:
            print(f"Wallet #{i}: {address}")
            print(f"  → Error checking status: {balance_info['error']}")
    
    if not wallets_to_deploy:
        print("\n✅ No wallets need activation!")
        return
    
    print(f"\n📋 Activation Summary:")
    print("=" * 50)
    for wallet_info in wallets_to_deploy:
        print(f"Wallet #{wallet_info['index']}: Needs activation → {wallet_info['address'][:10]}...{wallet_info['address'][-6:]}")
    print("=" * 50)
    print(f"✅ Wallets to activate: {len(wallets_to_deploy)}")
    print(f"💳 Funding wallet balance: {main_balance:.4f} TON")
    print("=" * 50)
    
    if main_balance < 0.01:
        print(f"\n⚠️ Funding wallet balance is very low. Please ensure it's funded.")

    proceed = input("Proceed with wallet activation? (y/n): ").lower().strip()
    if proceed != 'y':
        print("Activation cancelled.")
        return
    
    print("\n🚀 Starting wallet activation concurrently...")
    
    tasks = [_activate_single_wallet(wallet_info) for wallet_info in wallets_to_deploy]
    results = await asyncio.gather(*tasks)
    
    successful_activations = sum(1 for r in results if r.get("success") and r.get("activated"))
    
    print(f"\n📊 Activation Summary:")
    print(f"Successfully activated: {successful_activations}/{len(wallets_to_deploy)}")
    
    if successful_activations > 0:
        print("🎉 Activation process completed!")
        print("💡 Note: It may take a few minutes for all wallets to show as 'active' in all explorers.")
    elif any(r.get("success") for r in results):
        print("✅ No new activations needed. Some wallets were already active.")
    else:
        print("❌ No wallets were successfully activated.")
