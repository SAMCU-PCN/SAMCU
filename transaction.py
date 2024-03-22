from typing import List

from bitcoinutils.keys import P2pkhAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import TxInput, Transaction, TxOutput

from identity import PCNParty


def gen_tx_in(tx_in_input: TxInput, id_sender: PCNParty, id_list: List[PCNParty], a: float, x_r: float) -> Transaction:
    # tx_in must hold at least n times eps coins plus a fee.

    id_sender_p2pkh = P2pkhAddress(id_sender.addr).to_script_pub_key()
    id_list_pks = [i.pk.to_hex() for i in id_list]
    r_scr = Script([f'OP_{len(id_list_pks)}', *id_list_pks,
                    f'OP_{len(id_list_pks)}', 'OP_CHECKMULTISIG'])

    output_list = [TxOutput(a, r_scr.to_p2sh_script_pub_key())]
    if x_r > 0:
        output_list.append(TxOutput(x_r, id_sender_p2pkh))

    tx_in = Transaction([tx_in_input], output_list)

    sig_sender = id_sender.sk.sign_input(tx_in, 0, id_sender_p2pkh)

    tx_in_input.script_sig = Script([sig_sender, id_sender.pk.to_hex()])

    return tx_in


def gen_tx_ep1(id_ins: List[PCNParty], id_outs: List[PCNParty], notifier_output_scr_p2sh: Script,
               tx_input: TxInput, eps, n, notifier_fee, t_c, delta) -> Transaction:
    out_list = []
    for _id in id_outs:
        script = Script(['OP_IF',
                         _id.pk.to_hex(), 'OP_CHECKSIGVERIFY', 3 * t_c + delta, 'OP_CHECKSEQUENCEVERIFY',
                         'OP_ENDIF'])
        out_list.append(TxOutput(n, script.to_p2sh_script_pub_key()))

    out_list.append(TxOutput(notifier_fee, notifier_output_scr_p2sh))

    tx_ep1 = Transaction([tx_input], out_list)

    id_in_pks = [i.pk.to_hex() for i in id_ins]

    r_scr = Script([f'OP_{len(id_in_pks)}', *id_in_pks,
                    f'OP_{len(id_in_pks)}', 'OP_CHECKMULTISIG'])

    unlock_script = [0x0]
    for i, _id in enumerate(id_ins):
        unlock_script.append(_id.sk.sign_input(tx_ep1, 0, r_scr))
    unlock_script.append(r_scr.to_hex())

    tx_input.script_sig = Script(unlock_script)
    return tx_ep1


def gen_tx_relay(tx_ep1_input: TxInput, FAs: set, multi_sg_outputs: List[Script], n_parties_in_SGs: List,
                 eps: int) -> Transaction:
    out_list = []
    for multi_sg_output, n_parties in zip(multi_sg_outputs, n_parties_in_SGs):
        out_list.append(TxOutput(n_parties * eps, multi_sg_output))

    tx_relay = Transaction([tx_ep1_input], out_list)

    r_scr = Script([f'OP_{len(FAs)}', *[i.pk.to_hex() for i in FAs],
                    f'OP_{len(FAs)}', 'OP_CHECKMULTISIG'])

    unlock_script = [0x0]
    for i, _id in enumerate(FAs):
        unlock_script.append(_id.sk.sign_input(tx_relay, 0, r_scr))
    unlock_script.append(r_scr.to_hex())

    tx_ep1_input.script_sig = Script(unlock_script)

    return tx_relay


def gen_tx_ep2(tx_relay_input: TxInput, sg_parties: List[PCNParty], id_outs: List[PCNParty], eps: int,
               t_c: int, delta: int) -> Transaction:
    out_list = []
    for _id in id_outs:
        script = Script(['OP_IF',
                         _id.pk.to_hex(), 'OP_CHECKSIGVERIFY', t_c + delta, 'OP_CHECKSEQUENCEVERIFY',
                         'OP_ENDIF'])
        out_list.append(TxOutput(eps, script.to_p2sh_script_pub_key()))

    tx_ep2 = Transaction([tx_relay_input], out_list)

    sg_pks = [p.pk.to_hex() for p in sg_parties]
    r_scr = Script([f'OP_{len(sg_pks)}', *sg_pks,
                    f'OP_{len(sg_pks)}', 'OP_CHECKMULTISIG'])

    unlock_script = [0x0]
    for i, _id in enumerate(sg_parties):
        unlock_script.append(_id.sk.sign_input(tx_ep2, 0, r_scr))
    unlock_script.append(r_scr.to_hex())

    tx_relay_input.script_sig = Script(unlock_script)

    return tx_ep2


def gen_tx_refund(tx_state_input: TxInput, sender: PCNParty, receiver: PCNParty, amount: float, T,
                  delta: int = 0x01) -> Transaction:
    sender_p2pkh = P2pkhAddress(sender.addr).to_script_pub_key()
    tx_out0 = TxOutput(amount, sender_p2pkh)
    tx = Transaction([tx_state_input], [tx_out0])

    r_scr = Script(['OP_IF',
                    'OP_2', sender.pk.to_hex(), receiver.pk.to_hex(), 'OP_2', 'OP_CHECKMULTISIGVERIFY',
                    delta, 'OP_CHECKSEQUENCEVERIFY',
                    'OP_ELSE',
                    receiver.pk.to_hex(), 'OP_CHECKSIGVERIFY', T, 'OP_CHECKLOCKTIMEVERIFY',
                    'OP_ENDIF'])

    unlock_script = [sender.sk.sign_input(tx, 0, r_scr), r_scr.to_hex()]
    tx_state_input.script_sig = Script(unlock_script)

    return tx


def gen_tx_pay1(tx_ep_input: TxInput, tx_state_input: TxInput, sender: PCNParty, receiver: PCNParty, amount: float,
                eps: float = 1, t_c: int = 2, T: int = 5, delta: int = 0x01) -> Transaction:
    receiver_p2pkh = P2pkhAddress(receiver.addr).to_script_pub_key()
    tx_out0 = TxOutput(amount + eps, receiver_p2pkh)
    tx = Transaction([tx_ep_input, tx_state_input], [tx_out0])

    r_scr = Script(['OP_IF',
                    receiver.pk.to_hex(), 'OP_CHECKSIGVERIFY', t_c + delta, 'OP_CHECKSEQUENCEVERIFY',
                    'OP_ENDIF'])

    tx_ep_input.script_sig = Script([receiver.sk.sign_input(tx, 0, r_scr), r_scr.to_hex()])

    r_scr = Script(['OP_IF',
                    'OP_2', sender.pk.to_hex(), receiver.pk.to_hex(), 'OP_2', 'OP_CHECKMULTISIGVERIFY',
                    delta, 'OP_CHECKSEQUENCEVERIFY',
                    'OP_ELSE',
                    receiver.pk.to_hex(), 'OP_CHECKSIGVERIFY', T, 'OP_CHECKLOCKTIMEVERIFY',
                    'OP_ENDIF'])
    unlock_script = [0x00, receiver.sk.sign_input(tx, 0, r_scr), sender.sk.sign_input(tx, 0, r_scr), r_scr.to_hex()]
    tx_state_input.script_sig = Script(unlock_script)

    return tx


def gen_tx_pay2(tx_ep_input: TxInput, tx_state_input: TxInput, sender: PCNParty, receiver: PCNParty, amount: float,
                eps: float = 1, t_c: int = 2, T: int = 5, delta: int = 0x01) -> Transaction:
    receiver_p2pkh = P2pkhAddress(receiver.addr).to_script_pub_key()
    tx_out0 = TxOutput(amount + eps, receiver_p2pkh)
    tx = Transaction([tx_ep_input, tx_state_input], [tx_out0])

    r_scr = Script(['OP_IF',
                    receiver.pk.to_hex(), 'OP_CHECKSIGVERIFY', 3 * t_c + delta, 'OP_CHECKSEQUENCEVERIFY',
                    'OP_ENDIF'])

    tx_ep_input.script_sig = Script([receiver.sk.sign_input(tx, 0, r_scr), r_scr.to_hex()])

    r_scr = Script(['OP_IF',
                    'OP_2', sender.pk.to_hex(), receiver.pk.to_hex(), 'OP_2', 'OP_CHECKMULTISIGVERIFY',
                    delta, 'OP_CHECKSEQUENCEVERIFY',
                    'OP_ELSE',
                    receiver.pk.to_hex(), 'OP_CHECKSIGVERIFY', T, 'OP_CHECKLOCKTIMEVERIFY',
                    'OP_ENDIF'])
    unlock_script = [0x00, receiver.sk.sign_input(tx, 0, r_scr), sender.sk.sign_input(tx, 0, r_scr), r_scr.to_hex()]
    tx_state_input.script_sig = Script(unlock_script)

    return tx


def gen_tx_state(tx_state_input: TxInput, sender: PCNParty, receiver: PCNParty, amount: float, sender_balance: float,
                 receiver_balance: float, fee: float,
                 t: int, delta: int = 0x01) -> Transaction:
    new_script = Script(['OP_IF',
                         'OP_2', sender.pk.to_hex(), receiver.pk.to_hex(), 'OP_2', 'OP_CHECKMULTISIGVERIFY',
                         delta, 'OP_CHECKSEQUENCEVERIFY',
                         'OP_ELSE',
                         sender.pk.to_hex(), 'OP_CHECKSIGVERIFY', t, 'OP_CHECKLOCKTIMEVERIFY',
                         'OP_ENDIF'])

    tx_out0 = TxOutput(amount, new_script.to_p2sh_script_pub_key())
    sender_p2pkh = P2pkhAddress(sender.addr).to_script_pub_key()
    receiver_p2pkh = P2pkhAddress(receiver.addr).to_script_pub_key()
    tx_out1 = TxOutput(sender_balance - amount - fee, sender_p2pkh)
    tx_out2 = TxOutput(receiver_balance, receiver_p2pkh)

    tx = Transaction([tx_state_input], [tx_out0, tx_out1, tx_out2])

    r_scr = Script(['OP_2', receiver.pk.to_hex(), sender.pk.to_hex(), 'OP_2', 'OP_CHECKMULTISIG'])
    unlock_script = [0x00, receiver.sk.sign_input(tx, 0, r_scr), sender.sk.sign_input(tx, 0, r_scr), r_scr.to_hex()]
    tx_state_input.script_sig = Script(unlock_script)

    return tx
