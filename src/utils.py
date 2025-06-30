import aiohttp
import asyncio
import base64
from typing import List, Dict, Tuple, Optional
from tonsdk.crypto import mnemonic_new
from tonsdk.contract.wallet import Wallets, WalletVersionEnum
from tonsdk.utils import bytes_to_b64str
from config import RPC_API


async def load_seeds() -> List[str]:
    """Load seeds from wallets.txt file"""
    try:
        with open("wallets.txt", "r") as f:
            seeds = [seed.strip() for seed in f.readlines()]
        return [seed for seed in seeds if seed]  # Filter empty lines
    except FileNotFoundError:
        return []


async def generate_seeds(number_of_seeds: int, filename: str, words: int = 24) -> None:
    """Generate seed phrases and save to a file"""
    with open(filename, "w") as f:
        for _ in range(number_of_seeds):
            seed = " ".join(mnemonic_new(words))
            f.write(seed + "\n")
    print(f"✅ Generated {number_of_seeds} seed phrases and saved to {filename}")


async def create_wallet_from_seed(seed: str) -> Tuple[str, object]:
    """Create wallet from seed phrase and return address and wallet object"""
    mnemonics = seed.split()
    _mnemonics, _pub_k, _priv_k, wallet = Wallets.from_mnemonics(mnemonics, WalletVersionEnum.v4r2, 0)
    address = wallet.address.to_string(True, True, False)
    return address, wallet


async def generate_random_address() -> str:
    """Generate a new random wallet address"""
    seed_phrase = " ".join(mnemonic_new(24))
    mnemonics = seed_phrase.split()
    _, _, _, wallet = Wallets.from_mnemonics(mnemonics, WalletVersionEnum.v4r2, 0)
    return wallet.address.to_string(True, True, False)


async def get_wallet_seqno(address: str) -> Dict:
    """Get sequence number for a wallet"""
    try:
        url = f"https://toncenter.com/api/v3/wallet"
        params = {
            "address": address,
            "api_key": RPC_API
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    seqno = data.get("seqno", 0)
                    return {
                        "success": True,
                        "seqno": seqno
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API Error: {response.status}"
                    }
                    
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception: {str(e)}"
        }


async def send_transaction_boc(boc: str) -> Dict:
    """Send transaction BOC to the network"""
    try:
        url = f"https://toncenter.com/api/v3/message"
        params = {"api_key": RPC_API}
        data = {"boc": boc}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if "result" in result or "message_hash" in result:
                        b64_hash = result.get("result") or result.get("message_hash")
                        try:
                            # Standard base64 decode, then hex encode for explorer URL
                            hex_hash = base64.b64decode(b64_hash).hex()
                            explorer_link = f"https://tonviewer.com/transaction/{hex_hash}"
                        except Exception:
                            explorer_link = "N/A"
                        
                        return {
                            "success": True,
                            "explorer_link": explorer_link
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                else:
                    response_text = await response.text()
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {response_text}"
                    }
                    
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception: {str(e)}"
        }


async def get_wallet_balance(address: str) -> Dict:
    """Get balance and status for a TON wallet address"""
    try:
        url = f"https://toncenter.com/api/v3/addressInformation"
        params = {
            "address": address,
            "api_key": RPC_API
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Parse balance and status
                    balance_nano = data.get("balance", "0")
                    balance_ton = float(balance_nano) / 1_000_000_000  # Convert nanoTON to TON
                    status = data.get("status", "unknown")
                    
                    return {
                        "success": True,
                        "balance_ton": balance_ton,
                        "balance_nano": balance_nano,
                        "status": status,
                        "data": data
                    }
                else:
                    response_text = await response.text()
                    return {
                        "success": False,
                        "error": f"API Error: {response.status}",
                        "response_text": response_text
                    }
                    
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception: {str(e)}"
        }


async def create_transfer_transaction(wallet, to_address: str, amount_ton: float, seqno: int) -> Optional[str]:
    """Create transfer transaction and return BOC"""
    try:
        amount_nanoton = int(amount_ton * 1_000_000_000)  # Convert TON to nanoTON
        
        transfer = wallet.create_transfer_message(
            to_addr=to_address,
            amount=amount_nanoton,
            seqno=seqno,
            payload="",  # Empty payload for simple transfer
            send_mode=3  # Standard send mode
        )
        
        # Convert message to BOC
        boc = bytes_to_b64str(transfer["message"].to_boc(False))
        return boc
        
    except Exception as e:
        raise Exception(f"Failed to create transaction: {str(e)}")


async def await_seqno_increment(address: str, initial_seqno: int, timeout: int = 60) -> bool:
    """Waits for the wallet's seqno to increment, confirming a transaction."""
    start_time = asyncio.get_event_loop().time()
    while True:
        # Check for timeout
        if asyncio.get_event_loop().time() - start_time > timeout:
            print(f"  ⏳ Timeout waiting for transaction confirmation.")
            return False

        # Get the latest seqno
        seqno_result = await get_wallet_seqno(address)
        if seqno_result["success"] and seqno_result["seqno"] > initial_seqno:
            return True
        
        # Wait before checking again
        await asyncio.sleep(2)
