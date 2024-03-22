from bitcoinutils.script import Script
from bitcoinutils.transactions import TxInput

from identity import PCNParty
from transaction import gen_tx_in, gen_tx_ep1, gen_tx_relay, gen_tx_ep2, gen_tx_refund, gen_tx_pay1, gen_tx_pay2, \
    gen_tx_state
from utils import Print_TX


class Channel:

    def __init__(self, user1: PCNParty, user2: PCNParty, transfer_value: int):
        self.user1 = user1
        self.user2 = user2
        self.transfer_value = transfer_value

    def to_dict(self):
        return {
            "user1": self.user1,
            "user2": self.user2,
            "transfer_value": self.transfer_value
        }


class SubGraph:
    def __init__(self, sg_name, channels):
        self.name = sg_name
        self.senders = set()
        self.receivers = set()
        self.search_by_sender_dict = {}

        for c in channels:
            self.senders.add(c.user1)
            self.receivers.add(c.user2)
            self.search_by_sender_dict[c.user1] = c

        self.parties = self.senders.union(self.receivers)
        self.NP = self.senders.intersection(self.receivers)
        self.KS = self.senders.difference(self.receivers)
        self.KR = self.receivers.difference(self.senders)
        self.KP = self.KS.union(self.KR)

    def find_channel_by_sender(self, sender: PCNParty):
        return self.search_by_sender_dict[sender]


class UpdateGraph:
    def __init__(self, channels: dict):

        # UG configs
        self.default_tx_in_input = TxInput('94d009dff936a23fd37fa92cd5ba1f10c5848ee92376540c63774cc230bbc760',
                                           1)
        self.default_tx_pre_state_input = TxInput('352459366c063d1dda6a930214eb0eb70e39b9ac0e6489dc1bdb85181d7035d6',
                                                  0)
        self.default_sender_balance = 10000
        self.default_receiver_balance = 10000
        self.eps = 1
        self.fee = 0
        self.t_c = 2
        self.T = 5
        self.delta = 0x01

        self.dealer = None
        self.SGs = []
        self.KP = None
        self.FAs = None
        self.notifier_output_scr = None
        self.notifier_output_scr_p2sh = None
        self.sg_multi_sig_p2sh_list = None
        self.n_parties_in_SG_list = None
        self.sg_multi_sigs = {}
        self.sg_multi_sig_p2shs = {}
        self.n_parties_in_SGs = {}
        self.channels = channels
        self.parties = {}
        self.senders = set()
        self.receivers = set()
        for c in channels.values():
            self.senders.add(c.user1)
            self.receivers.add(c.user2)
        self.parties = {i.name: i for i in self.senders.union(self.receivers)}

        self.user_save_infos = {}

        self.tx_ins = {}
        self.tx_ep1s = {}
        self.tx_relays = {}
        self.tx_ep2s = {}
        self.tx_pays = {}
        self.tx_refunds = {}
        self.tx_states = {}

        return

    def select_dealer(self, dealer_name):

        if dealer_name in self.parties.keys():
            self.dealer = self.parties[dealer_name]
            print(f"Select {dealer_name} as the dealer")
        else:
            print(f"Can not find the dealer, dealer_name:{dealer_name}")
            print(self.parties)

    def get_channel_by_name(self, channel_name):
        return self.channels[channel_name]

    def get_user_by_name(self, user_name):
        return self.parties[user_name]

    def split_graph(self, sub_graph_channels: list):

        self.KP = set()
        for i, channels in enumerate(sub_graph_channels):
            sg_name = f"SG{i + 1}"
            print(f"Construct {sg_name}")
            sg = SubGraph(sg_name, [self.get_channel_by_name(i) for i in channels])
            self.KP = self.KP.union(sg.KP)

            self.SGs.append(sg)
            self.n_parties_in_SGs[sg_name] = len(sg.parties)

    def create_p1_txs(self):

        for sg in self.SGs:
            for sg_kp in sg.KP:
                sg_kp.create_fresh_address()

        self.FAs = self.KP

        self.notifier_output_scr = Script([f'OP_{len(self.FAs)}', *[p.fresh_pk.to_hex() for p in self.FAs],
                                           f'OP_{len(self.FAs)}', 'OP_CHECKMULTISIG'])
        self.notifier_output_scr_p2sh = self.notifier_output_scr.to_p2sh_script_pub_key()

        self.sg_multi_sigs = {}
        self.sg_multi_sig_p2shs = {}
        for sg in self.SGs:
            sg_parties = [p.pk.to_hex() for p in sg.parties]
            self.sg_multi_sigs[sg.name] = Script([f'OP_{len(sg_parties)}', *sg_parties,
                                                  f'OP_{len(sg_parties)}', 'OP_CHECKMULTISIG'])
            self.sg_multi_sig_p2shs[sg.name] = self.sg_multi_sigs[sg.name].to_p2sh_script_pub_key()

        self.sg_multi_sig_p2sh_list = list(self.sg_multi_sig_p2shs.values())
        self.n_parties_in_SG_list = [self.n_parties_in_SGs[sg] for sg in self.sg_multi_sig_p2shs.keys()]

        self.user_save_infos = {}

    def create_p2_txs(self):

        print("generating tx ep1...")
        for sg in self.SGs:

            self.tx_ins[sg.name] = []
            self.tx_ep1s[sg.name] = []

            sg_senders = list(sg.senders)
            sg_receivers = list(sg.receivers)

            for r in sg.receivers:
                txin_cash = 1000
                c_i = len(sg.receivers)

                tx_in = gen_tx_in(self.default_tx_in_input,
                                  r,
                                  [r, *sg_senders, *sg.KP],
                                  (len(self.channels) + c_i) * self.eps,
                                  txin_cash - (len(self.channels) + c_i) * self.eps - self.fee)
                self.tx_ins[sg.name].append(tx_in)

                tx_ep1 = gen_tx_ep1([r, *sg_senders, *sg.KP],
                                    sg_receivers,
                                    self.notifier_output_scr_p2sh,
                                    TxInput(tx_in.get_hash(), 0), self.eps, len(self.channels), c_i, self.t_c,
                                    self.delta)
                self.tx_ep1s[sg.name].append(tx_ep1)

        return

    def create_p3_txs(self):

        print("generating tx relays...")
        for sg in self.SGs:
            print(sg.name)
            self.tx_relays[sg.name] = []
            # for kp in sg.KP:
            for kp in list(sg.KP)[:1]:
                sg_tx_ep1s = self.tx_ep1s[sg.name]
                for tx_ep1 in sg_tx_ep1s:
                    tx_relay = gen_tx_relay(TxInput(tx_ep1.get_hash(), 0), self.FAs, self.sg_multi_sig_p2sh_list,
                                            self.n_parties_in_SG_list, self.eps)
                    # Print_TX(tx_relay, "relay")
                    self.tx_relays[sg.name].append(tx_relay)

        print("generating tx ep2...")
        for sg in self.SGs:
            print(sg.name)
            self.tx_ep2s[sg.name] = []
            # for kp in sg.KP:
            for kp in list(sg.KP)[:1]:
                for sg_name, tx_relays in self.tx_relays.items():
                    if sg_name != sg.name:
                        for tx_relay in tx_relays:
                            tx_ep2 = gen_tx_ep2(TxInput(tx_relay.get_hash(), 0), sg.parties, sg.receivers, self.eps,
                                                self.t_c, self.delta)
                            Print_TX(tx_ep2, "relay")
                            self.tx_ep2s[sg.name].append(tx_ep2)

    def create_p4_txs(self):
        for sg in self.SGs:
            for sender in sg.senders:

                self.tx_states[sender.name] = []
                self.tx_refunds[sender.name] = []
                self.tx_pays[sender.name] = []

                channel = sg.find_channel_by_sender(sender)
                tx_state = gen_tx_state(self.default_tx_pre_state_input, sender, channel.user2, channel.transfer_value,
                                        self.default_sender_balance, self.default_receiver_balance, self.fee,
                                        self.T, self.delta)
                tx_refund = gen_tx_refund(TxInput(tx_state.get_hash(), 0), sender, channel.user2,
                                          channel.transfer_value, self.T, self.delta)
                self.tx_states[sender.name].append(tx_state)
                self.tx_refunds[sender.name].append(tx_refund)

                for tx_ep in self.tx_ep1s[sg.name]:
                    tx_pay = gen_tx_pay1(TxInput(tx_ep.get_hash(), 0), TxInput(tx_state.get_hash(), 0), sender,
                                         channel.user2, channel.transfer_value, self.eps, self.t_c, self.T, self.delta)
                    self.tx_pays[sender.name].append(tx_pay)

                for tx_ep in self.tx_ep2s[sg.name]:
                    tx_pay = gen_tx_pay2(TxInput(tx_ep.get_hash(), 0), TxInput(tx_state.get_hash(), 0), sender,
                                         channel.user2, channel.transfer_value, self.eps, self.t_c, self.T, self.delta)
                    self.tx_pays[sender.name].append(tx_pay)

        print("Finish generating P4")
