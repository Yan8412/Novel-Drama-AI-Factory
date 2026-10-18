import hashlib
import unittest
from novel_drama_candidate.qa_feedback import (
    motion_load, check_evidence_claim, force_causal_chain,
    prop_lifecycle, qa_feedback_map, review_prompt_edit)

SHA = 'A' * 64

def evidence(event, kind='OBSERVED'):
    return dict(kind=kind, event=event, source_sha256=SHA, pts_s=[1.0, 1.1], ref='synthetic.json#record')

def prop(frame, state):
    return dict(object_id='p', frame=frame, pts_s=frame/24, screen_state=state,
                source_sha256=SHA, ref='synthetic.json#frame', visible_tip_px=123 if state=='VISIBLE' else 0)

def prompt_review(source, effective, **kwargs):
    return review_prompt_edit(source, effective,
        expected_source_sha256=hashlib.sha256(source).hexdigest(),
        expected_effective_sha256=hashlib.sha256(effective).hexdigest(),
        required_clauses=('Keep approved motion.',), **kwargs)


def bound_chain():
    """Synthetic, upstream-reviewed identity links and disjoint observations."""
    c=dict(id='c', actor='helper', recipient='mover', interaction_id='lift-1',
           contact_id='grip-1', support_before_id='platform', support_after_id='rail')
    windows={'force_source':[0.2,0.3], 'contact':[0,0.1], 'body_response':[0.4,0.5],
             'support_before':[0,0.5], 'transfer':[1,2], 'support_after':[2,3]}
    for key,event in [('force_source','FORCE_SOURCE'),('contact','CONTACT'),
                      ('body_response','BODY_RESPONSE'),('support_before','SUPPORT_BEFORE'),
                      ('support_after','SUPPORT_AFTER'),('transfer','SUPPORT_TRANSFER')]:
        c[key]=evidence(event)
        c[key].update(pts_s=windows[key], interaction_id=c['interaction_id'],
                      ref='synthetic.json#'+key, actor=c['recipient'])
    for key in ('force_source','contact'):
        c[key].update(actor=c['actor'],recipient=c['recipient'],contact_id=c['contact_id'])
    c['body_response']['contact_id']=c['contact_id']
    c['support_before']['support_id']=c['support_before_id']
    c['support_after']['support_id']=c['support_after_id']
    c['transfer'].update(from_support_id=c['support_before_id'],to_support_id=c['support_after_id'])
    return c


class EvidenceFeedbackTest(unittest.TestCase):
    def test_contact_not_off_lid(self):
        self.assertEqual(check_evidence_claim('FOOT_OFF_LID', evidence('FOOT_CONTACT'))['status'], 'UNVERIFIED')
    def test_visible_not_world_birth(self):
        self.assertEqual(check_evidence_claim('WORLD_BIRTH', evidence('FIRST_VISIBLE'))['status'], 'UNVERIFIED')
    def test_palm_not_forearm_load(self):
        self.assertEqual(check_evidence_claim('FOREARM_LOAD', evidence('PALM_CONTACT'))['status'], 'UNVERIFIED')
    def test_grip_not_active_force(self):
        self.assertEqual(check_evidence_claim('ACTIVE_ASSISTANCE', evidence('GRIP'))['status'], 'UNVERIFIED')
    def test_direct_observation_scoped_pass(self):
        result=check_evidence_claim('PALM_CONTACT', evidence('PALM_CONTACT'))
        self.assertEqual(result['status'], 'PASS'); self.assertFalse(result['production_admitted'])
    def test_inference_not_observation(self):
        self.assertEqual(check_evidence_claim('FOOT_OFF_LID', evidence('FOOT_OFF_LID','INFERRED'))['status'],'UNVERIFIED')
    def test_unknown_time_not_invented(self):
        self.assertEqual(check_evidence_claim('PALM_CONTACT', {'kind':'UNKNOWN','pts_s':None})['status'],'UNVERIFIED')
    def test_malformed_pts_controlled(self):
        for value in ([True,2],[-1,2],[2,1],[0,float('nan')],['one','two']):
            e=evidence('PALM_CONTACT');e['pts_s']=value
            self.assertEqual(check_evidence_claim('PALM_CONTACT',e)['status'],'BLOCKED')
    def test_bad_source_binding_blocked(self):
        e=evidence('PALM_CONTACT');e['source_sha256']='x'
        self.assertEqual(check_evidence_claim('PALM_CONTACT',e)['status'],'BLOCKED')
    def test_force_missing_support_not_pass(self):
        r=force_causal_chain([dict(id='c',actor='a',contact=evidence('CONTACT'))])
        self.assertEqual(r['status'],'UNVERIFIED')
    def test_force_full_records_scoped(self):
        c=bound_chain()
        self.assertEqual(force_causal_chain([c])['status'],'PASS')
    def test_force_bad_records_controlled(self):
        self.assertEqual(force_causal_chain([None])['status'],'BLOCKED')
    def test_maintained_support_not_new_actions(self):
        rows=[dict(id=str(i),actor='a',kind=k,begin_s=0,end_s=4,description='synthetic') for i,k in enumerate(['ACTIVE_EVENT','MAINTAINED_SUPPORT','MAINTAINED_SUPPORT'])]
        r=motion_load(rows,4000); self.assertEqual(r['active_event_count'],1);self.assertEqual(r['maintained_support_count'],2)
    def test_load_limit_warn_only(self):
        rows=[dict(id=str(i),actor='a',kind='ACTIVE_EVENT',begin_s=0,end_s=4,description='synthetic') for i in range(4)]
        self.assertEqual(motion_load(rows,4000)['status'],'WARN')
    def test_empty_load_unknown(self):
        self.assertEqual(motion_load([],4000)['status'],'UNVERIFIED')
    def test_repeated_event_not_double_counted_or_silent(self):
        e=dict(id='x',actor='a',kind='ACTIVE_EVENT',begin_s=0,end_s=1,description='synthetic')
        self.assertEqual(motion_load([e,e],4000)['status'],'BLOCKED')
    def test_large_tip_adjacent_absence_fails(self):
        r=prop_lifecycle([prop(11,'VISIBLE'),prop(12,'UNSEEN')],[dict(object_id='p',before_frame=11,after_frame=12)])
        self.assertEqual(r['screen_status'],'FAIL');self.assertEqual(r['world_status'],'UNVERIFIED')
    def test_sparse_sample_cannot_cover_critical_pair(self):
        r=prop_lifecycle([prop(10,'VISIBLE'),prop(12,'UNSEEN')],[dict(object_id='p',before_frame=11,after_frame=12)])
        self.assertTrue(any(x['rule']=='CRITICAL_PAIR_MISSING' for x in r['findings']))
    def test_claimed_hidden_exit_requires_evidence(self):
        r=prop_lifecycle([prop(1,'VISIBLE'),prop(2,'EXITED')],[])
        self.assertEqual(r['screen_status'],'UNVERIFIED');self.assertEqual(r['world_status'],'UNVERIFIED')
    def test_visible_never_proves_world_persistence(self):
        r=prop_lifecycle([prop(1,'VISIBLE'),prop(2,'VISIBLE')],[])
        self.assertEqual(r['world_status'],'UNVERIFIED')
    def test_malformed_prop_controlled(self):
        for rows in ([None],[{'frame':[]}],{'x':1},None): self.assertEqual(prop_lifecycle(rows,[])['status'],'BLOCKED')
    def test_prompt_freeze_injection_fails(self):
        r=prompt_review(b'Keep approved motion.',b'Keep approved motion. Freeze the final 1 second.')
        self.assertEqual(r['status'],'FAIL')
    def test_prompt_landscape_conflict_fails(self):
        r=prompt_review(b'Keep approved motion.',b'Keep approved motion. 9:16 landscape.')
        self.assertEqual(r['status'],'FAIL')
    def test_unapproved_fact_cannot_enter_prompt(self):
        r=prompt_review(b'Keep approved motion.',b'Keep approved motion.',provenance=[dict(kind='DESIGN_ASSUMPTION')])
        self.assertNotEqual(r['status'],'PASS')
    def test_unknown_semantic_change_requires_review(self):
        r=prompt_review(b'Keep approved motion.',b'Keep approved motion. He adds a step.')
        self.assertEqual(r['status'],'HUMAN_REVIEW')
    def test_unchanged_prompt_scoped_pass(self):
        r=prompt_review(b'Keep approved motion.',b'Keep approved motion.')
        self.assertEqual(r['status'],'HUMAN_REVIEW');self.assertEqual(r['fidelity']['status'],'PASS');self.assertFalse(r['production_admitted'])
    def test_unbound_approved_fact_label_not_authority(self):
        r=prompt_review(b'Keep approved motion.',b'Keep approved motion.',provenance=[dict(kind='APPROVED_FACT')])
        self.assertEqual(r['status'],'HUMAN_REVIEW')
    def test_malformed_prompt_inputs_controlled(self):
        self.assertEqual(review_prompt_edit(None,None)['status'],'BLOCKED')
    def test_feedback_existing_constraint_not_missing(self):
        r=qa_feedback_map([self.feedback(constraint_status='MISSING')]);self.assertEqual(r['status'],'FAIL')
    def test_feedback_contract_change_not_prompt_eligible(self):
        r=qa_feedback_map([self.feedback(change_scope='REFERENCE_CHANGE')]);self.assertFalse(r['records'][0]['prompt_eligible']);self.assertEqual(r['status'],'HUMAN_REVIEW')
    def test_feedback_unknown_pts_unverified(self):
        self.assertEqual(qa_feedback_map([self.feedback(pts_s=None)])['status'],'UNVERIFIED')
    def test_feedback_binding_and_present_failure_preserved(self):
        r=qa_feedback_map([self.feedback()]);self.assertEqual(r['status'],'PASS');self.assertEqual(r['records'][0]['constraint_status'],'PRESENT_BUT_OUTPUT_FAILED')
    def test_unknown_quality_not_feedback_pass(self):
        r=qa_feedback_map([self.feedback(observed_status='INCONCLUSIVE',constraint_status='PRESENT')])
        self.assertEqual(r['status'],'UNVERIFIED')
    def test_failed_output_not_fabricated(self):
        r=qa_feedback_map([self.feedback(observed_status='UNVERIFIED')]);self.assertEqual(r['status'],'FAIL')
    def test_pass_cannot_be_relabelled_output_failure(self):
        r=qa_feedback_map([self.feedback(observed_status='PASS')]);self.assertEqual(r['status'],'FAIL')
    def test_absent_constraint_not_relabelled_present(self):
        r=qa_feedback_map([self.feedback(constraint_present_in_source=False,constraint_status='PRESENT')])
        self.assertEqual(r['status'],'FAIL')
    def test_ambiguous_constraint_not_pass(self):
        r=qa_feedback_map([self.feedback(constraint_status='AMBIGUOUS')]);self.assertEqual(r['status'],'UNVERIFIED')
    def test_point_event_keeps_zero_duration(self):
        e=dict(id='p',actor='a',kind='ACTIVE_EVENT',begin_s=1,end_s=1,description='synthetic point')
        r=motion_load([e],4000);self.assertEqual(r['point_event_count'],1)
    def test_mixed_prop_sources_blocked(self):
        a,b=prop(1,'VISIBLE'),prop(2,'VISIBLE');b['source_sha256']='B'*64
        self.assertEqual(prop_lifecycle([a,b],[])['status'],'BLOCKED')
    def test_frame_pts_reverse_fails(self):
        a,b=prop(1,'VISIBLE'),prop(2,'VISIBLE');a['pts_s']=2;b['pts_s']=1
        self.assertEqual(prop_lifecycle([a,b],[])['screen_status'],'FAIL')
    def test_exit_cause_other_video_not_accepted(self):
        a,b=prop(1,'VISIBLE'),prop(2,'EXITED');b['cause_evidence']=evidence('EXITED');b['cause_evidence']['source_sha256']='B'*64
        self.assertEqual(prop_lifecycle([a,b],[])['screen_status'],'UNVERIFIED')
    def test_reversed_causal_evidence_fails(self):
        c=dict(id='c',actor='a',contact=evidence('CONTACT'),body_response=evidence('BODY_RESPONSE'))
        c['contact']['pts_s']=[2,3]
        self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_huge_malformed_timestamp_controlled(self):
        e=evidence('PALM_CONTACT');e['pts_s']=[0,10**1000]
        self.assertEqual(check_evidence_claim('PALM_CONTACT',e)['status'],'BLOCKED')
    def test_huge_duration_controlled(self):
        e=dict(id='p',actor='a',kind='ACTIVE_EVENT',begin_s=1,end_s=1,description='synthetic point')
        self.assertEqual(motion_load([e],10**400)['status'],'BLOCKED')
    def test_existing_portrait_landscape_conflict_rejected(self):
        text=b'Keep approved motion. 9:16 landscape.'
        self.assertEqual(prompt_review(text,text)['status'],'FAIL')
    def test_existing_freeze_conflict_rejected(self):
        text=b'Keep approved motion. Freeze final 1second.'
        self.assertEqual(prompt_review(text,text)['status'],'FAIL')
    def test_prop_ms_conversion_overflow_controlled(self):
        r=prop(1,'VISIBLE');r['pts_s']=1e308
        self.assertEqual(prop_lifecycle([r],[])['status'],'BLOCKED')
    def test_reversed_support_sequence_fails(self):
        c=dict(id='c',actor='a',support_before=evidence('SUPPORT_BEFORE'),transfer=evidence('SUPPORT_TRANSFER'),support_after=evidence('SUPPORT_AFTER'))
        c['support_before']['pts_s']=[9,10];c['transfer']['pts_s']=[8,9];c['support_after']['pts_s']=[0,1]
        self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_overlapping_support_windows_unverified_not_fail(self):
        c=dict(id='c',actor='a',support_before=evidence('SUPPORT_BEFORE'),transfer=evidence('SUPPORT_TRANSFER'),support_after=evidence('SUPPORT_AFTER'))
        c['support_before']['pts_s']=[0,2];c['transfer']['pts_s']=[1,2];c['support_after']['pts_s']=[1.5,3]
        r=force_causal_chain([c]);self.assertEqual(r['status'],'UNVERIFIED')
        self.assertTrue(any(x['rule']=='SUPPORT_TRANSFER_ORDER_UNCERTAIN' for x in r['findings']))
    def feedback(self,**changes):
        row=dict(qa_id='G',historical_prompt_sha256=SHA,candidate_prompt_sha256=SHA,source_sha256=SHA,pts_s=[11/24,12/24],ref='synthetic#tail',observed_status='FAIL',constraint_status='PRESENT_BUT_OUTPUT_FAILED',constraint_present_in_source=True,change_scope='TEXT_ONLY',expected_mechanism='reorganize only; no quality guarantee')
        row.update(changes);return row


class ReviewRegressionTest(unittest.TestCase):
    def test_review_overlap_cannot_prove_order(self):
        c=bound_chain()
        for key in ('force_source','contact'):c[key]['pts_s']=[0.5,1.0]
        c['body_response']['pts_s']=[0,1]
        self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_either_overlapping_cause_is_unverified(self):
        for key in ('force_source','contact'):
            with self.subTest(key=key):
                c=bound_chain();c[key]['pts_s']=[0.3,0.6]
                self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_touching_cause_response_is_unverified(self):
        c=bound_chain();c['force_source']['pts_s']=[0.2,0.4]
        self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_simultaneous_point_events_are_unverified(self):
        c=bound_chain();c['force_source']['pts_s']=[0.4,0.4];c['body_response']['pts_s']=[0.4,0.4]
        self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_reversed_cause_remains_fail(self):
        c=bound_chain();c['force_source']['pts_s']=[0.6,0.7]
        self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_ordered_bound_chain_scoped_pass(self):
        r=force_causal_chain([bound_chain()])
        self.assertEqual(r['status'],'PASS');self.assertFalse(r['production_admitted'])
    def test_missing_chain_binding_is_unverified(self):
        for field in ('recipient','interaction_id','contact_id','support_before_id','support_after_id'):
            with self.subTest(field=field):
                c=bound_chain();del c[field]
                self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_missing_observation_binding_is_unverified(self):
        for key,field in (('force_source','actor'),('force_source','recipient'),('contact','contact_id'),
                          ('body_response','actor'),('body_response','contact_id'),
                          ('support_before','support_id'),('support_after','support_id'),
                          ('transfer','from_support_id'),('transfer','to_support_id'),('transfer','interaction_id')):
            with self.subTest(key=key,field=field):
                c=bound_chain();del c[key][field]
                self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_unknown_identity_cannot_match_itself(self):
        for value in (None,'UNKNOWN','UNVERIFIED'):
            with self.subTest(value=value):
                c=bound_chain();c['interaction_id']=value
                for key in ('force_source','contact','body_response','support_before','support_after','transfer'):c[key]['interaction_id']=value
                self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_malformed_chain_binding_blocked(self):
        for value in ([],{},True,9,''):
            with self.subTest(value=value):
                c=bound_chain();c['recipient']=value
                self.assertEqual(force_causal_chain([c])['status'],'BLOCKED')
    def test_malformed_observation_binding_blocked(self):
        for value in ([],{},True,9,''):
            with self.subTest(value=value):
                c=bound_chain();c['contact']['actor']=value
                self.assertEqual(force_causal_chain([c])['status'],'BLOCKED')
    def test_other_force_actor_cannot_stitch(self):
        c=bound_chain();c['force_source']['actor']='bystander'
        self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_other_force_recipient_cannot_stitch(self):
        c=bound_chain();c['force_source']['recipient']='bystander'
        self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_other_contact_partner_cannot_stitch(self):
        c=bound_chain();c['contact']['recipient']='bystander'
        self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_other_response_actor_cannot_stitch(self):
        c=bound_chain();c['body_response']['actor']='bystander'
        self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_other_contact_identity_cannot_stitch(self):
        for key in ('force_source','contact','body_response'):
            with self.subTest(key=key):
                c=bound_chain();c[key]['contact_id']='grip-2'
                self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_other_support_actor_cannot_stitch(self):
        for key in ('support_before','support_after','transfer'):
            with self.subTest(key=key):
                c=bound_chain();c[key]['actor']='bystander'
                self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_other_support_object_cannot_stitch(self):
        for key in ('support_before','support_after'):
            with self.subTest(key=key):
                c=bound_chain();c[key]['support_id']='unrelated-object'
                self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_other_transfer_support_cannot_stitch(self):
        for field in ('from_support_id','to_support_id'):
            with self.subTest(field=field):
                c=bound_chain();c['transfer'][field]='unrelated-object'
                self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_same_video_other_interaction_cannot_stitch(self):
        for key in ('force_source','contact','body_response','support_before','support_after','transfer'):
            with self.subTest(key=key):
                c=bound_chain();c[key]['interaction_id']='independent-lift'
                self.assertEqual(force_causal_chain([c])['status'],'FAIL')
    def test_unknown_observation_remains_unverified(self):
        c=bound_chain();c['force_source']['kind']='UNKNOWN'
        self.assertEqual(force_causal_chain([c])['status'],'UNVERIFIED')
    def test_parallel_actor_chains_are_allowed(self):
        a,b=bound_chain(),bound_chain();b.update(id='d',actor='helper-b',recipient='mover-b',interaction_id='lift-b')
        for key in ('force_source','contact','body_response','support_before','support_after','transfer'):
            b[key].update(interaction_id=b['interaction_id'],actor=b['recipient'])
        for key in ('force_source','contact'):b[key].update(actor=b['actor'],recipient=b['recipient'])
        self.assertEqual(force_causal_chain([a,b])['status'],'PASS')
    def test_self_assistance_is_not_automatically_rejected(self):
        c=bound_chain();c['actor']=c['recipient']
        for key in ('force_source','contact'):c[key]['actor']=c['actor']
        self.assertEqual(force_causal_chain([c])['status'],'PASS')
    def test_bound_failure_does_not_justify_rewrite(self):
        r=qa_feedback_map([EvidenceFeedbackTest().feedback()]);row=r['records'][0]
        self.assertEqual(r['status'],'PASS');self.assertFalse(row['prompt_eligible'])
        self.assertEqual(row.get('binding_status'),'PASS');self.assertTrue(row.get('text_review_in_scope'))
        self.assertEqual(row.get('rewrite_status'),'HUMAN_REVIEW');self.assertFalse(row['director_approved'])
    def test_claimed_mechanism_or_gap_is_not_reviewed_rewrite(self):
        row=EvidenceFeedbackTest().feedback(constraint_present_in_source=False,constraint_status='MISSING',expected_mechanism='Caller says add a clause',reviewed=True)
        r=qa_feedback_map([row]);self.assertFalse(r['records'][0]['prompt_eligible'])
        self.assertEqual(r['records'][0].get('rewrite_status'),'HUMAN_REVIEW')
    def test_uncertain_feedback_not_text_review_eligible(self):
        row=qa_feedback_map([EvidenceFeedbackTest().feedback(pts_s=None)])['records'][0]
        self.assertFalse(row['prompt_eligible']);self.assertFalse(row.get('text_review_in_scope'))
        self.assertEqual(row.get('binding_status'),'UNVERIFIED')

if __name__=='__main__':unittest.main()
