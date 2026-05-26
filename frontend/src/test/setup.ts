import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, vi } from 'vitest';

const warningAllowlist: RegExp[] = [];

function formatConsoleArgs(args: unknown[]): string {
	return args
		.map((arg) => {
			if (typeof arg === 'string') {
				return arg;
			}
			try {
				return JSON.stringify(arg);
			} catch {
				return String(arg);
			}
		})
		.join(' ');
}

function isAllowedWarning(message: string): boolean {
	return warningAllowlist.some((pattern) => pattern.test(message));
}

let unexpectedWarnings: string[] = [];
let unexpectedErrors: string[] = [];
let warnSpy: ReturnType<typeof vi.spyOn> | null = null;
let errorSpy: ReturnType<typeof vi.spyOn> | null = null;

beforeEach(() => {
	unexpectedWarnings = [];
	unexpectedErrors = [];

	const originalWarn = console.warn.bind(console);
	const originalError = console.error.bind(console);

	warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args: unknown[]) => {
		const message = formatConsoleArgs(args);
		if (!isAllowedWarning(message)) {
			unexpectedWarnings.push(message);
		}
		originalWarn(...args);
	});

	errorSpy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
		const message = formatConsoleArgs(args);
		if (!isAllowedWarning(message)) {
			unexpectedErrors.push(message);
		}
		originalError(...args);
	});
});

afterEach(() => {
	warnSpy?.mockRestore();
	errorSpy?.mockRestore();
	warnSpy = null;
	errorSpy = null;

	if (unexpectedWarnings.length === 0 && unexpectedErrors.length === 0) {
		return;
	}

	const warningDump = unexpectedWarnings.map((message) => `WARN: ${message}`).join('\n');
	const errorDump = unexpectedErrors.map((message) => `ERROR: ${message}`).join('\n');
	const combined = [warningDump, errorDump].filter(Boolean).join('\n');

	throw new Error(`Unexpected console warning/error detected during test:\n${combined}`);
});
