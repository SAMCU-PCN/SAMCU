from bitcoinutils.script import Script
from bitcoinutils.transactions import TxInput

from identity import BlockID, PCNParty
from protocol import Channel, UpdateGraph
from transaction import *
from utils import *
from identity import *


def main():
    users = []
    for i in range(14):
        user_name = f"U{i + 1}"
        user_id = BlockID()
        users.append(PCNParty(user_name, user_id.sk, user_id.pk, user_id.addr))

    update_channels = {
        "channel1": Channel(users[0], users[1], 1000),
        "channel2": Channel(users[1], users[2], 1000),
        "channel3": Channel(users[2], users[3], 1000),
        "channel4": Channel(users[3], users[4], 1000),
        "channel5": Channel(users[4], users[5], 1000),
        "channel6": Channel(users[5], users[6], 1000),
        "channel7": Channel(users[7], users[8], 1000),
        "channel8": Channel(users[8], users[9], 1000),
        "channel9": Channel(users[9], users[10], 1000),
        "channel10": Channel(users[10], users[11], 1000),
        "channel11": Channel(users[11], users[12], 1000),
        "channel12": Channel(users[12], users[13], 1000)
    }
    ug = UpdateGraph(update_channels)
    ug.select_dealer("U1")
    ug.split_graph([["channel1", "channel2", "channel7", "channel8"],
                    ["channel3", "channel4", "channel9", "channel10"],
                    ["channel5", "channel6", "channel11", "channel12"],
                    ])
    ug.create_p1_txs()
    ug.create_p2_txs()
    ug.create_p3_txs()
    ug.create_p4_txs()


def mock_key_party_computation(n_channels, n_sgs, n_FAs):
    # 1 txin+ 1 txep1 + 1 txr + 1 txstate + 1 txp1 + n/m txrelay + n-n/m txep2

    n_member_in_SG = int(n_channels / n_sgs)

    users = []
    for i in range(n_channels + 1):
        user_name = f"U{i + 1}"
        user_id = BlockID()
        users.append(PCNParty(user_name, user_id.sk, user_id.pk, user_id.addr))

    update_channels = {f"channel{i + 1}": Channel(users[i], users[i + 1], 100000) for i in range(n_channels)}
    sg_parties = users[:n_member_in_SG]

    default_tx_in_input = TxInput('94d009dff936a23fd37fa92cd5ba1f10c5848ee92376540c63774cc230bbc760',
                                  1)
    eps = 1
    fee = 0
    t_cd = 2
    t_cd2 = 3

    FAs = users[:int((n_sgs + 1) * n_FAs / 2)]

    notifier_output_scr = Script([f'OP_{len(FAs)}', *[p.pk.to_hex() for p in FAs],
                                  f'OP_{len(FAs)}', 'OP_CHECKMULTISIG'])
    notifier_output_scr_p2sh = notifier_output_scr.to_p2sh_script_pub_key()

    txin_cash = 1000
    n = 100  # to-do

    tx_in = gen_tx_in(default_tx_in_input,
                      users[0],
                      [users[0], *users[:n_member_in_SG]],
                      n * eps,
                      txin_cash - n * eps - fee)

    tx_ep1 = gen_tx_ep1([users[0], *users[:n_member_in_SG]],
                        users[:n_member_in_SG],
                        notifier_output_scr_p2sh,
                        TxInput(tx_in.get_hash(), 0), eps, t_cd)

    tx_relay = gen_tx_relay(TxInput(tx_ep1.get_hash(), 0), set(FAs),
                            [Script([f'OP_{len(sg_parties)}', *[p.pk.to_hex() for p in sg_parties],
                                     f'OP_{len(sg_parties)}', 'OP_CHECKMULTISIG'])] * n_sgs, [n_member_in_SG] * n_sgs,
                            eps)


if __name__ == "__main__":
    main()

    # mock_key_party_computation(100, 10, 2)
