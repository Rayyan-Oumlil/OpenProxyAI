import React from 'react';
import Content from '@theme-original/DocSidebar/Desktop/Content';
import type ContentType from '@theme/DocSidebar/Desktop/Content';
import type {WrapperProps} from '@docusaurus/types';

import SidebarSearch from '@site/src/components/SidebarSearch';

type Props = WrapperProps<typeof ContentType>;

export default function ContentWrapper(props: Props): React.JSX.Element {
  return (
    <SidebarSearch sidebar={props.sidebar}>
      <Content {...props} />
    </SidebarSearch>
  );
}
