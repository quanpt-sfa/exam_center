import type { EntityConfig, EntityGroup } from '../types';
import { resolveDisplayLabel } from '../utils/displayLabel';
import { useLocale } from '../../../app/locale';

const groupLabels: Record<EntityGroup, string> = {
  Core: 'Danh mục dùng chung',
  Academic: 'Học thuật',
  People: 'Con người',
  Facility: 'Cơ sở vật chất',
};

export function EntityNavigation({
  entities,
  activeKey,
  onSelect,
}: {
  entities: EntityConfig[];
  activeKey: EntityConfig['key'];
  onSelect: (key: EntityConfig['key']) => void;
}) {
  const { locale } = useLocale();
  const groups = entities.reduce<Record<EntityGroup, EntityConfig[]>>(
    (current, entity) => {
      current[entity.group].push(entity);
      return current;
    },
    { Core: [], Academic: [], People: [], Facility: [] }
  );

  return (
    <aside className="master-data-sidebar" aria-label="Master data groups">
      {Object.entries(groups).map(([group, items]) => {
        if (items.length === 0) {
          return null;
        }
        return (
          <div key={group}>
            <p className="eyebrow" style={{ margin: '0 0 6px' }}>{groupLabels[group as EntityGroup]}</p>
            {items.map((config) => (
              <button
                className={config.key === activeKey ? 'master-data-tab is-active' : 'master-data-tab'}
                key={config.key}
                type="button"
                onClick={() => onSelect(config.key)}
              >
                {resolveDisplayLabel(config.label, locale)}
              </button>
            ))}
          </div>
        );
      })}
    </aside>
  );
}