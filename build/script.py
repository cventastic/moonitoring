import time
import copy
import os
from substrateinterface import SubstrateInterface

# test outside container
# network = "moonbeam"
# network = "moonriver"

network = os.environ['NETWORK']

if network == "moonbeam":
    from networks import members_moonbeam as members
    from networks import url_moonbeam as url
    from networks import collator_slots_moonbeam as collator_slots
if network == "moonriver":
    from networks import members_moonriver as members
    from networks import url_moonriver as url
    from networks import collator_slots_moonriver as collator_slots

conn = SubstrateInterface(
    url=url
)


def get_round(ws_provider):
    active_round = ws_provider.query(
        module='ParachainStaking',
        storage_function='Round',
        params=[]
    )
    return {"current": active_round['current'], "first": active_round['first'], "length": active_round['length']}


def get_round_end(ws_provider, first_block, length):
    current_block = ws_provider.get_block()
    blocks_into_round = int(str(current_block['header']['number'])) - int(str(first_block))
    blocks_until_end = int(str(length)) - blocks_into_round
    time_to_end = blocks_until_end * 12
    return {"seconds": time_to_end, "minutes": time_to_end / 60, "blocks": blocks_until_end }


def get_all_collators(ws_provider):
    candidate_pool_info = ws_provider.query(
        module='ParachainStaking',
        storage_function='CandidatePool',
        params=[]
    )
    all_collators_sorted = sorted(candidate_pool_info, key=lambda item: item.get("amount"), reverse=True)
    return all_collators_sorted


def add_ranks(collators):
    c = 0
    ranking = []
    for i in collators:
        c = c + 1
        i.update({'rank': c})
        ranking.append(i)
    return ranking


def get_member_ranks(collators):
    dict_list = []
    for i in collators:
        for k, v in members.items():
            if v.lower() == (i['owner']):
                dict_list.append({"member": k, "owner": v, "amount": i['amount'], "rank": i['rank']})
    return dict_list


def get_scheduled_delegations(ws_provider, collators, current_round):
    list_of_dicts = []
    for i in collators:
        # print(i['address'])
        scheduled_delegations = ws_provider.query(
            module='ParachainStaking',
            storage_function='DelegationScheduledRequests',
            params=[i['owner']]
        )
        if scheduled_delegations:
            unbond_amount = 0
            for x in scheduled_delegations:
                if x['when_executable'] < current_round:
                    unbond_amount = unbond_amount + int(str(x['action'][1]))
            list_of_dicts.append({i['owner']: unbond_amount})
    return list_of_dicts


def update_delegations(unbonds, all_collators):
    for x in all_collators:
        for i in unbonds:
            for k, v in i.items():
                if str(k.lower()) == str(x['owner']).lower():
                    new_bond = int(x['amount']) - v
                    x['amount'] = new_bond
    all_collators_sorted = sorted(all_collators, key=lambda item: item.get("amount"), reverse=True)
    return all_collators_sorted


while True:
    all_collators = get_all_collators(conn)
    current_round = get_round(conn)
    tte = get_round_end(conn, current_round['first'], current_round['length'])
    # get_round_end(conn)

    # copy because reference is mutated in add_ranks function
    ac = copy.deepcopy(all_collators)
    all_collator_ranking = add_ranks(ac)
    all_members_ranking = get_member_ranks(all_collator_ranking)

    # calculate unbonds only for members
    unbonds = get_scheduled_delegations(conn, all_members_ranking, current_round['current'])
    # calculate unbonds for all collators
    # unbonds = get_scheduled_delegations(conn, all_collator_ranking, current_round['current'])
    updated_delegations = update_delegations(unbonds, all_collators)

    ranking_after_unbond = add_ranks(updated_delegations)
    ranking_after_unbond_member = get_member_ranks(ranking_after_unbond)

    last_spot_amount = 0
    waiting_list_amount = 0

    for i in updated_delegations:
        if i['rank'] == collator_slots:
            last_spot_amount = round(i['amount'] / 1000000000000000000, 2)
        if i['rank'] == collator_slots + 1:
            waiting_list_amount = round(i['amount'] / 1000000000000000000, 2)

    print("---", "round minutes:", tte['minutes'], " seconds:", tte['seconds'], " blocks:", tte['blocks'], "---")
    # print("After unbonds for members of cdf: ")
    for i in all_members_ranking:
        for x in ranking_after_unbond_member:
            if x['member'] == i['member']:
                rounded_amount_before = round(i['amount'] / 1000000000000000000, 2)
                rounded_amount_after = round(x['amount'] / 1000000000000000000, 2)
                # print(i['member'], "stake: ", rounded_amount_before, "rank: ", i['rank'], \
                #          "stake_after_unbonds: ", rounded_amount_after, "rank_after_unbonds: ", x['rank'])
                if last_spot_amount != 0 and waiting_list_amount != 0:
                    if x['rank'] >= 50:
                        distance_last_spot = rounded_amount_after - last_spot_amount
                        distance_waiting_list = rounded_amount_after - waiting_list_amount
                        print(x['member'], "rank: ", x['rank'])
                        print("distance last collator: ", round(distance_last_spot, 2))
                        print("distance to waiting list: ", round(distance_waiting_list, 2), "\n")

