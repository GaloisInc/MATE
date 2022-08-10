import { Button, Form, OverlayTrigger, Popover } from "react-bootstrap";

interface AdvancedMenuProps {
  memoryLimitMB: number;
  timeLimitSeconds: number;
  onChangeMemoryLimit: (memoryLimit: number) => void;
  onChangeTimeLimit: (timeLimit: number) => void;
}

export const AdvancedMenu = ({
  memoryLimitMB,
  timeLimitSeconds,
  onChangeMemoryLimit,
  onChangeTimeLimit,
}: AdvancedMenuProps) => {
  const popover = (
    <Popover id="advanced-menu">
      <Popover.Title as="h3">Advanced options</Popover.Title>
      <Popover.Content>
        <Form.Group controlId="memoryLimit">
          <Form.Control
            as="input"
            type="number"
            onChange={(e) => onChangeMemoryLimit(Number(e.target.value))}
            value={memoryLimitMB}
          />
          <Form.Text className="text-muted">
            Enter a value &gt; 0 to limit memory used in MB
          </Form.Text>
        </Form.Group>
        <Form.Group controlId="timeLimit">
          <Form.Control
            as="input"
            type="number"
            onChange={(e) => onChangeTimeLimit(Number(e.target.value))}
            value={timeLimitSeconds}
          />
          <Form.Text className="text-muted">
            Enter a value &gt; 0 to limit time in seconds
          </Form.Text>
        </Form.Group>
      </Popover.Content>
    </Popover>
  );

  return (
    <OverlayTrigger trigger="click" placement="left" overlay={popover}>
      <Button>advanced</Button>
    </OverlayTrigger>
  );
};
