import {describe,it,expect} from 'vitest';
import {InputActivity} from '../../src/lib/voice/activity';
describe('PCM-duration activity detection',()=>{
 it('requires 80ms onset, rejects isolated clicks, and ends after 350ms silence',()=>{
  const a=new InputActivity();
  expect(a.push(640,true).started).toBe(false);a.push(640,false);
  for(let i=0;i<3;i++)expect(a.push(640,true).started).toBe(false);
  expect(a.push(640,true).started).toBe(true);
  for(let i=0;i<17;i++)expect(a.push(640,false).ended).toBe(false);
  expect(a.push(640,false).ended).toBe(true);expect(a.active).toBe(false);
 });
 it('counts audio duration independently of callback spacing and resets partial onsets',()=>{
  const a=new InputActivity();expect(a.push(3200,true).started).toBe(true);
  a.reset();expect(a.push(1280,true).started).toBe(false);a.reset();
  expect(a.push(1280,true).started).toBe(false);expect(a.push(1280,true).started).toBe(true);
 });
});
