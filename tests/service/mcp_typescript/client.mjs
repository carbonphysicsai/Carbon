// Real independent SDK transport fixture. No model calls or scientific evidence.
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';

const launch = JSON.parse(process.argv[2]);
const prefix = 'carbon_research_v2__';
const operationId = 'typescript-business-operation-0001';
const practice = {
  operation_id: operationId,
  kind: 'practice',
  strategy: { parameters: { steps: 512 } },
  action: null,
  arguments: null,
  hypothesis: 'Test the independent TypeScript transport with an admitted fixture',
  expected_effect: 'One durable proposal charge across process restart',
};

async function connected(exercise) {
  const transport = new StdioClientTransport({ ...launch, stderr: 'pipe' });
  // Drain server diagnostics, which are not part of protocol output.
  transport.stderr?.on('data', () => {});
  const client = new Client({ name: 'carbon-typescript-interop', version: '1.0.0' });
  try {
    await client.connect(transport);
    await exercise(client);
  } finally {
    await client.close();
  }
}

await connected(async (client) => {
  const { tools } = await client.listTools();
  assert.equal(tools.length, 12);
  assert(tools.every((tool) => tool.name.startsWith(prefix)));
  const start = tools.find((tool) => tool.name === `${prefix}start_research_task`);
  assert.equal(start.inputSchema.additionalProperties, false);
  assert('strategy' in start.inputSchema.properties);
  assert(!('strategy_json' in start.inputSchema.properties));
  assert(!('principal' in start.inputSchema.properties));
  assert(start.outputSchema);

  const { resources } = await client.listResources();
  assert.deepEqual(resources.map((item) => item.uri).sort(), [
    'carbon://research/v1/capabilities',
    'carbon://research/v1/guidance',
    'carbon://research/v2/guidance',
    'skill://carbon/carbon-research-v1/SKILL.md',
    'skill://carbon/carbon-research-v1/references/workflow.md',
  ]);
  const capabilities = await client.readResource({ uri: 'carbon://research/v1/capabilities' });
  assert.equal(JSON.parse(capabilities.contents[0].text).audience, 'miner');
  const guidance = await client.readResource({ uri: 'carbon://research/v1/guidance' });
  assert.match(guidance.contents[0].text, /operation_id stable/);
  const prompt = await client.getPrompt({ name: 'carbon_research_workflow_v1' });
  assert.match(prompt.messages[0].content.text, /DEVELOPMENT/);
  const current = await client.readResource({ uri: 'carbon://research/v2/guidance' });
  assert.match(current.contents[0].text, /tasks\/get/);

  const call = (operation, args) => client.callTool({ name: prefix + operation, arguments: args });
  const first = await call('start_research_task', practice);
  const repeated = await call('start_research_task', practice);
  assert(!first.isError);
  assert(!repeated.isError);
  assert.deepEqual(first.structuredContent, repeated.structuredContent);
  assert.equal(first.structuredContent.official_eligible, false);
  assert.equal(first.structuredContent.payload.reply.used_trials, 1);
  assert(first.content.some((item) => item.type === 'text'));
  for (const invalid of [
    { ...practice, principal: 'another-user' },
    { ...practice, strategy: JSON.stringify(practice.strategy) },
  ]) {
    assert.equal((await call('start_research_task', invalid)).isError, true);
  }
  const stopped = await call('get_prior', { operation_id: operationId });
  assert.equal(stopped.isError, true);
  assert.match(JSON.stringify(stopped.content), /OPERATIONAL_STOP/);
  assert(!JSON.stringify(stopped.content).includes('private-controller-detail'));
});

await connected(async (client) => {
  const repeated = await client.callTool({ name: `${prefix}start_research_task`, arguments: practice });
  assert(!repeated.isError);
  assert.equal(repeated.structuredContent.payload.reply.used_trials, 1);
  const conflict = await client.callTool({
    name: `${prefix}start_research_task`,
    arguments: { ...practice, strategy: { parameters: { steps: 1024 } } },
  });
  assert.equal(conflict.isError, true);
});

process.stdout.write(JSON.stringify({
  client: '@modelcontextprotocol/client',
  version: '2.0.0',
  transport: 'stdio',
  fixture_only: true,
  server_restarts: 1,
  used_trials: 1,
  checks: ['discovery', 'resources', 'prompt', 'structured_tool_result', 'strict_inputs', 'redaction', 'durable_retry', 'restart', 'conflict'],
}) + '\n');
