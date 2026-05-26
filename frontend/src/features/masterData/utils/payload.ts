import type { MasterDataRow } from '../api/contracts';
import type { EntityConfig, EntityFormState } from '../types';

export function buildInitialForm(config: EntityConfig): EntityFormState {
  return Object.fromEntries(config.fields.map((field) => [field.name, field.defaultValue ?? '']));
}

export function buildFormFromRow(config: EntityConfig, row: MasterDataRow): EntityFormState {
  return Object.fromEntries(
    config.fields.map((field) => {
      const value = row[field.name];
      return [field.name, value == null ? field.defaultValue ?? '' : String(value)];
    })
  );
}