import { Dialog, Tabs, Typography, Flex, useMediaQuery } from '@neo4j-ndl/react';
import graphenhancement from '../../../assets/images/graph-enhancements.svg';
import { Dispatch, SetStateAction, useState } from 'react';
import DeletePopUpForOrphanNodes from './DeleteTabForOrphanNodes';
import deleteOrphanAPI from '../../../services/DeleteOrphanNodes';
import NewEntityExtractionSetting from './EnitityExtraction/NewEntityExtractionSetting';
import { useFileContext } from '../../../context/UsersFiles';
import DeduplicationTab from './Deduplication';
import { tokens } from '@neo4j-ndl/base';
import PostProcessingCheckList from './PostProcessingCheckList';
import AdditionalInstructionsText from './AdditionalInstructions';
import { OptionType } from '../../../types';

export default function GraphEnhancementDialog({
  open,
  onClose,
  combinedPatterns,
  setCombinedPatterns,
  combinedNodes,
  setCombinedNodes,
  combinedRels,
  setCombinedRels,
}: {
  open: boolean;
  onClose: () => void;
  combinedPatterns: string[];
  setCombinedPatterns: Dispatch<SetStateAction<string[]>>;
  combinedNodes: OptionType[];
  setCombinedNodes: Dispatch<SetStateAction<OptionType[]>>;
  combinedRels: OptionType[];
  setCombinedRels: Dispatch<SetStateAction<OptionType[]>>;
}) {
  const { breakpoints } = tokens;
  const [orphanDeleteAPIloading, setorphanDeleteAPIloading] = useState<boolean>(false);
  const {
    setShowTextFromSchemaDialog,
    setSchemaLoadDialog,
    setPredefinedSchemaDialog,
    setUserDefinedPattern,
    setUserDefinedNodes,
    setUserDefinedRels,
    setDbPattern,
    setDbNodes,
    setDbRels,
    setSchemaValNodes,
    setSchemaValRels,
    setSchemaTextPattern,
    setPreDefinedNodes,
    setPreDefinedRels,
    setPreDefinedPattern,
    setSelectedPreDefOption,
    allPatterns,
    setDataImporterSchemaDialog,
    setImporterNodes,
    setImporterPattern,
    setImporterRels,
  } = useFileContext();
  const isTablet = useMediaQuery(`(min-width:${breakpoints.xs}) and (max-width: ${breakpoints.lg})`);

  const orphanNodesDeleteHandler = async (selectedEntities: string[]) => {
    try {
      setorphanDeleteAPIloading(true);
      await deleteOrphanAPI(selectedEntities);
      setorphanDeleteAPIloading(false);
    } catch (error) {
      setorphanDeleteAPIloading(false);
      console.log(error);
    }
  };

  const handleOnclose = () => {
    if (allPatterns.length > 0) {
      onClose();
      return;
    }
    // User
    setUserDefinedPattern([]);
    setUserDefinedNodes([]);
    setUserDefinedRels([]);
    // DB
    setDbPattern([]);
    setDbNodes([]);
    setDbRels([]);
    // Text
    setSchemaTextPattern([]);
    setSchemaValNodes([]);
    setSchemaValRels([]);
    // Predefined
    setPreDefinedNodes([]);
    setPreDefinedRels([]);
    setPreDefinedPattern([]);
    // combined Nodes and rels
    setCombinedNodes([]);
    setCombinedRels([]);
    setCombinedPatterns([]);
    // Data Importer
    setImporterNodes([]);
    setImporterPattern([]);
    setImporterRels([]);
    setSelectedPreDefOption(null);
    onClose();
  };

  const [activeTab, setactiveTab] = useState<number>(0);
  return (
    <Dialog
      modalProps={{
        id: 'graph-enhancement-popup',
        className: 'n-p-token-4 n-rounded-lg',
      }}
      isOpen={open}
      size='unset'
      hasDisabledCloseButton={false}
      onClose={handleOnclose}
    >
      <Dialog.Header className='flex justify-between self-end mb-0! '>
        <div className='n-bg-palette-neutral-bg-weak px-4'>
          <div className='flex! flex-row items-center mb-2'>
            <img
              src={graphenhancement}
              style={{
                width: isTablet ? 170 : 220,
                height: isTablet ? 170 : 220,
                marginRight: 10,
                objectFit: 'contain',
              }}
              loading='lazy'
              alt='graph-enhancement-options-logo'
            />
            <div className='flex flex-col'>
              <Typography variant={isTablet ? 'h5' : 'h2'}>Graph Enhancements</Typography>
              <Typography variant={isTablet ? 'subheading-small' : 'subheading-medium'} className='mb-2'>
                {isTablet
                  ? `This set of tools will help you enhance the quality of your Knowledge Graph`
                  : `This set of tools will help you enhance the quality of your Knowledge Graph by removing possible
                duplicated entities, disconnected nodes and set a Graph Schema for improving the quality of the entity
                extraction process`}
              </Typography>
              <Flex className='pt-2'>
                <Tabs fill='underline' onChange={setactiveTab} size={isTablet ? 'small' : 'large'} value={activeTab}>
                  <Tabs.Tab
                    tabId={0}
                    htmlAttributes={{
                      'aria-label': 'Entity Extraction Settings',
                    }}
                  >
                    Entity Extraction Settings
                  </Tabs.Tab>
                  <Tabs.Tab
                    tabId={1}
                    htmlAttributes={{
                      'aria-label': 'Additional Instructions',
                    }}
                  >
                    Additional Instructions
                  </Tabs.Tab>
                  <Tabs.Tab
                    tabId={2}
                    htmlAttributes={{
                      'aria-label': 'Disconnected Nodes',
                    }}
                  >
                    Disconnected Nodes
                  </Tabs.Tab>
                  <Tabs.Tab
                    tabId={3}
                    htmlAttributes={{
                      'aria-label': 'Duplication Nodes',
                    }}
                  >
                    De-Duplication Of Nodes
                  </Tabs.Tab>
                  <Tabs.Tab
                    tabId={4}
                    htmlAttributes={{
                      'aria-label': 'Post Processing Jobs',
                    }}
                  >
                    Post Processing Jobs
                  </Tabs.Tab>
                </Tabs>
              </Flex>
            </div>
          </div>
        </div>
      </Dialog.Header>
      <Dialog.Content className='flex flex-col n-gap-token- grow w-[90%] mx-auto'>
        <Tabs.TabPanel className='n-flex n-flex-col n-gap-token-4' value={activeTab} tabId={0}>
          <div className='w-[80%] mx-auto'>
            <NewEntityExtractionSetting
              view='Tabs'
              openTextSchema={() => {
                setShowTextFromSchemaDialog({ triggeredFrom: 'enhancementtab', show: true });
              }}
              openLoadSchema={() => setSchemaLoadDialog({ triggeredFrom: 'enhancementtab', show: true })}
              openPredefinedSchema={() => {
                setPredefinedSchemaDialog({ triggeredFrom: 'enhancementtab', show: true });
              }}
              closeEnhanceGraphSchemaDialog={onClose}
              settingView='headerView'
              combinedPatterns={combinedPatterns}
              setCombinedPatterns={setCombinedPatterns}
              combinedNodes={combinedNodes}
              setCombinedNodes={setCombinedNodes}
              combinedRels={combinedRels}
              setCombinedRels={setCombinedRels}
              openDataImporterSchema={() => {
                setDataImporterSchemaDialog({ triggeredFrom: 'enhancementtab', show: true });
              }}
            />
          </div>
        </Tabs.TabPanel>
        <Tabs.TabPanel className='n-flex n-flex-col n-gap-token-4 n-p-token-6' value={activeTab} tabId={1}>
          <AdditionalInstructionsText closeEnhanceGraphSchemaDialog={onClose} />
        </Tabs.TabPanel>
        <Tabs.TabPanel className='n-flex n-flex-col n-gap-token-4 n-p-token-6' value={activeTab} tabId={2}>
          <DeletePopUpForOrphanNodes deleteHandler={orphanNodesDeleteHandler} loading={orphanDeleteAPIloading} />
        </Tabs.TabPanel>
        <Tabs.TabPanel className='n-flex n-flex-col n-gap-token-4 n-p-token-6' value={activeTab} tabId={3}>
          <DeduplicationTab />
        </Tabs.TabPanel>
        <Tabs.TabPanel className='n-flex n-flex-col n-gap-token-4 n-p-token-6' value={activeTab} tabId={4}>
          <PostProcessingCheckList />
        </Tabs.TabPanel>
      </Dialog.Content>
    </Dialog>
  );
}
