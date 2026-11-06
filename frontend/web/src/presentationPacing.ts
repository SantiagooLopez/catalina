// Visual pacing requested for the demonstration; not backend latency.
const delays = [6000, 7000, 9000];
let lastDelay = -1;
export async function paceResponse(started: number) {
  const choices = delays.filter(ms => ms !== lastDelay);
  const target = choices[Math.floor(Math.random() * choices.length)];
  lastDelay = target;
  const remaining = target - (performance.now() - started);
  if (remaining > 0) await new Promise(resolve => setTimeout(resolve, remaining));
}
