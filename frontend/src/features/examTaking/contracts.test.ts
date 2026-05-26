import { describe, expect, test } from 'vitest';

import {
  isEditableTextMode,
  isFileUploadMode,
  isUnsupportedAnswerMode,
  normalizeAnswerMode,
} from './contracts';

describe('examTaking answer mode helpers', () => {
  test('text and textarea remain editable text', () => {
    expect(normalizeAnswerMode('TEXT')).toBe('TEXT');
    expect(normalizeAnswerMode('TEXTAREA')).toBe('TEXTAREA');
    expect(isEditableTextMode('TEXT')).toBe(true);
    expect(isEditableTextMode('TEXTAREA')).toBe(true);
  });

  test('sql and code text remain editable text but not file upload', () => {
    expect(normalizeAnswerMode('SQL_TEXT')).toBe('SQL_TEXT');
    expect(normalizeAnswerMode('CODE_TEXT')).toBe('CODE_TEXT');
    expect(isEditableTextMode('SQL_TEXT')).toBe(true);
    expect(isEditableTextMode('CODE_TEXT')).toBe(true);
    expect(isFileUploadMode('SQL_TEXT')).toBe(false);
  });

  test('json is editable only when backend explicitly says json', () => {
    expect(normalizeAnswerMode('JSON')).toBe('JSON');
    expect(isEditableTextMode('JSON')).toBe(true);
  });

  test('file upload never becomes text', () => {
    expect(normalizeAnswerMode('FILE_UPLOAD')).toBe('FILE_UPLOAD');
    expect(isFileUploadMode('FILE_UPLOAD')).toBe(true);
    expect(isEditableTextMode('FILE_UPLOAD')).toBe(false);
  });

  test('database and foundation-only modes remain non-editable', () => {
    expect(normalizeAnswerMode('STUDENT_DATABASE')).toBe('STUDENT_DATABASE');
    expect(normalizeAnswerMode('FOUNDATION_ONLY')).toBe('FOUNDATION_ONLY');
    expect(isEditableTextMode('STUDENT_DATABASE')).toBe(false);
    expect(isEditableTextMode('FOUNDATION_ONLY')).toBe(false);
    expect(isUnsupportedAnswerMode('STUDENT_DATABASE')).toBe(true);
    expect(isUnsupportedAnswerMode('FOUNDATION_ONLY')).toBe(true);
  });

  test('instruction and capture only modes remain non-editable', () => {
    expect(isEditableTextMode('INSTRUCTION_ONLY')).toBe(false);
    expect(isEditableTextMode('CAPTURE_ONLY')).toBe(false);
    expect(isUnsupportedAnswerMode('INSTRUCTION_ONLY')).toBe(true);
    expect(isUnsupportedAnswerMode('CAPTURE_ONLY')).toBe(true);
  });

  test('unknown modes never become editable text', () => {
    expect(normalizeAnswerMode('FUTURE_AI_WORKSPACE')).toBe('UNSUPPORTED');
    expect(isEditableTextMode('FUTURE_AI_WORKSPACE')).toBe(false);
    expect(isUnsupportedAnswerMode('FUTURE_AI_WORKSPACE')).toBe(true);
  });
});