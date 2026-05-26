import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('UE2E seed wrapper safety', () => {
  beforeEach(() => {
    delete process.env.UE2E_RUN_INTEGRATION;
    delete process.env.UE2E_AUTH_MODE;
    delete process.env.UE2E_PYTHON;
  });

  it('rejects machine-token mode when integration or bearer mode is missing', async () => {
    const mod = await import('../../e2e/support/seed');

    process.env.UE2E_RUN_INTEGRATION = '0';
    process.env.UE2E_AUTH_MODE = 'bearer';
    expect(() => mod.buildSeedAuthPrincipalsArgs()).toThrow(
      'UE2E_RUN_INTEGRATION=1 and UE2E_AUTH_MODE=bearer'
    );

    process.env.UE2E_RUN_INTEGRATION = '1';
    process.env.UE2E_AUTH_MODE = 'cookie';
    expect(() => mod.buildSeedAuthPrincipalsArgs()).toThrow(
      'UE2E_RUN_INTEGRATION=1 and UE2E_AUTH_MODE=bearer'
    );
  });

  it('uses --emit-tokens in machine bearer integration mode and does not log stdout', async () => {
    const mod = await import('../../e2e/support/seed');

    process.env.UE2E_RUN_INTEGRATION = '1';
    process.env.UE2E_AUTH_MODE = 'bearer';

    const adminToken = ['ey', 'Jadmin.header.payload'].join('');
    const ownerToken = ['ey', 'Jowner.header.payload'].join('');
    const nonOwnerToken = ['ey', 'Jnonowner.header.payload'].join('');

    const payload = {
      scenario: 'seed_auth_principals',
      token_type: 'bearer',
      token_output: 'raw_machine_mode',
      principals: {
        admin: { username: 'ue2e_admin', user_id: 1, person_id: 11, student_id: null, roles: ['ADMIN'] },
        owner: { username: 'ue2e_owner', user_id: 2, person_id: 22, student_id: 222, roles: ['STUDENT'] },
        non_owner: {
          username: 'ue2e_non_owner',
          user_id: 3,
          person_id: 33,
          student_id: 333,
          roles: ['STUDENT'],
        },
      },
      tokens: {
        admin_access_token: adminToken,
        owner_access_token: ownerToken,
        non_owner_access_token: nonOwnerToken,
      },
    };

    const runner = vi.fn(() => ({
      status: 0,
      stdout: `${JSON.stringify(payload)}\n`,
      stderr: '',
    }));

    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const result = mod.seedAuthPrincipalsWithRunner(runner);

    expect(result.tokens.owner_access_token).toBe(ownerToken);
    expect(result.token_output).toBe('raw_machine_mode');

    const seedCallArgs = runner.mock.calls[0]?.[1] as string[];
    expect(seedCallArgs).toContain('seed-auth-principals');
    expect(seedCallArgs).toContain('--emit-tokens');
    expect(consoleSpy).not.toHaveBeenCalled();

    consoleSpy.mockRestore();
  });

  it('redacts jwt-like output in seed-helper failure text', async () => {
    const mod = await import('../../e2e/support/seed');

    const jwtLike = ['ey', 'Jabc.def.ghi'].join('');

    const sanitized = mod.sanitizeSeedHelperFailure(
      `owner_access_token=${jwtLike} dsn=postgresql://user:pass@db.local/exam password=abc`
    );

    expect(sanitized).not.toContain(jwtLike);
    expect(sanitized).toContain('<redacted-jwt>');
    expect(sanitized).toContain('dsn=<redacted>');
    expect(sanitized).toContain('password=<redacted>');
  });
});
