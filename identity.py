from bitcoinutils.keys import P2pkhAddress, PrivateKey
import setup as Init
from utils import Gen_Secret

Init.initNetwork()


class BlockID:
    """
    Helper class for handling identity related keys and addresses easily
    """

    def __init__(self):
        rand = Gen_Secret()
        self.sk = PrivateKey(secret_exponent=int(rand, 16))
        self.pk = self.sk.get_public_key()
        self.addr = self.pk.get_address().to_string()
        self.p2pkh = P2pkhAddress(self.addr).to_script_pub_key()


class PCNParty:
    def __init__(self, name, sk, pk, addr):
        self.name = name
        self.sk = sk
        self.pk = pk
        self.addr = addr
        self.fresh_sk = None
        self.fresh_pk = None
        self.fresh_addr = None

    def __repr__(self):
        return f"user_name:{self.name} \nuser_address:{self.addr}\n"

    def create_fresh_address(self):
        fresh_id = BlockID()
        self.fresh_sk = fresh_id.sk
        self.fresh_pk = fresh_id.pk
        self.fresh_addr = fresh_id.addr
