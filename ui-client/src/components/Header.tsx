import React from "react";
import { Navbar, Nav, NavDropdown } from "react-bootstrap";
import { LinkContainer } from "react-router-bootstrap";
import { FaChess } from "react-icons/fa";
import { BiHelpCircle } from "react-icons/bi";

import "../styles/Header.scss";

interface HeaderProps {
  buildId?: string;
  binaryName?: string;
}

export const Header: React.FC<HeaderProps> = ({ buildId, binaryName }) => {
  return (
    <Navbar className="Header" variant="dark">
      <Nav className="me-auto">
        <LinkContainer to="/">
          <Navbar.Brand>
            <FaChess />
            MATE
          </Navbar.Brand>
        </LinkContainer>
        <LinkContainer to="/compilations" activeClassName="selected">
          <Nav.Link>Compilations</Nav.Link>
        </LinkContainer>
        <LinkContainer to="/builds" activeClassName="selected">
          <Nav.Link>Builds</Nav.Link>
        </LinkContainer>
        <LinkContainer to="/snapshots" activeClassName="selected">
          <Nav.Link>Flowfinder Snapshots</Nav.Link>
        </LinkContainer>
        <NavDropdown title="For Experts" id="expert-nav-dropdown">
          <NavDropdown.Item>
            <LinkContainer to="/rest-api" activeClassName="selected">
              <Nav.Link>REST API</Nav.Link>
            </LinkContainer>
          </NavDropdown.Item>
          <NavDropdown.Item>
            <LinkContainer to="/notebooks" activeClassName="selected">
              <Nav.Link>Notebooks</Nav.Link>
            </LinkContainer>
          </NavDropdown.Item>
        </NavDropdown>
      </Nav>
      <Nav>
        {buildId && (
          <Navbar.Collapse className="justify-content-end">
            <Navbar.Text>build: {buildId}</Navbar.Text>
          </Navbar.Collapse>
        )}
        {binaryName && (
          <Navbar.Collapse className="justify-content-end">
            <Navbar.Text>binary: {binaryName}</Navbar.Text>
          </Navbar.Collapse>
        )}
        <Nav.Link
          href="http://mate.galois.com/master/using-flowfinder.html"
          target="_doc"
        >
          <BiHelpCircle size="1.4em" />
        </Nav.Link>
      </Nav>
    </Navbar>
  );
};
