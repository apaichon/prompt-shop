import {afterEach,expect,it,vi} from 'vitest';
import type {BrowserAudio} from '../../src/lib/voice/audio';
import {queueWelcome,takeWelcome,cancelWelcome,registerWelcomeCancel} from '../../src/lib/voice/welcome';
afterEach(()=>cancelWelcome());
it('hands prepared output off once and closes a replaced or cancelled pending context',()=>{
 const a={close:vi.fn()} as unknown as BrowserAudio,b={close:vi.fn()} as unknown as BrowserAudio;
 queueWelcome(a);queueWelcome(b);expect(a.close).toHaveBeenCalledOnce();expect(takeWelcome()).toBe(b);expect(takeWelcome()).toBeUndefined();b.close();
 const stop=vi.fn(),unregister=registerWelcomeCancel(stop);cancelWelcome();expect(stop).toHaveBeenCalledOnce();unregister();cancelWelcome();expect(stop).toHaveBeenCalledOnce();
});
