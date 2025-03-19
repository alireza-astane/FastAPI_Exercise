import strawberry
from fastapi import FastAPI, Depends
from strawberry.fastapi import GraphQLRouter
from neo4j import GraphDatabase

# Neo4j Connection
NEO4J_URI = "bolt://localhost:7687"  # Change if using a remote instance
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password_here"


class Neo4jConnection:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def query(self, query, parameters=None):
        with self.driver.session() as session:
            return session.run(query, parameters).data()


db = Neo4jConnection(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)


# GraphQL Types
@strawberry.type
class Person:
    name: str
    age: int
    friends: list["Person"]  # This will represent the friends of the person


# GraphQL Queries
@strawberry.type
class Query:
    @strawberry.field
    def get_person(self, name: str) -> Person:
        """Retrieve a person by name"""
        query = """
        MATCH (p:Person {name: $name}) 
        OPTIONAL MATCH (p)-[:FRIEND]->(f:Person)
        RETURN p.name AS name, p.age AS age, COLLECT(f.name) AS friends
        """
        result = db.query(query, {"name": name})
        if result:
            person = result[0]
            return Person(
                name=person["name"], age=person["age"], friends=person["friends"]
            )
        return None

    @strawberry.field
    def get_all_people(self) -> list[Person]:
        """Retrieve all people"""
        query = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[:FRIEND]->(f:Person)
        RETURN p.name AS name, p.age AS age, COLLECT(f.name) AS friends
        """
        result = db.query(query)
        people = []
        for person in result:
            people.append(
                Person(
                    name=person["name"], age=person["age"], friends=person["friends"]
                )
            )
        return people


# GraphQL Mutations
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_person(self, name: str, age: int) -> Person:
        """Create a new Person node"""
        query = """
        CREATE (p:Person {name: $name, age: $age})
        RETURN p.name AS name, p.age AS age
        """
        result = db.query(query, {"name": name, "age": age})
        if result:
            return Person(name=result[0]["name"], age=result[0]["age"], friends=[])
        return None

    @strawberry.mutation
    def create_friendship(self, name1: str, name2: str) -> str:
        """Create a FRIEND relationship between two persons"""
        query = """
        MATCH (p1:Person {name: $name1}), (p2:Person {name: $name2})
        MERGE (p1)-[:FRIEND]->(p2)
        MERGE (p2)-[:FRIEND]->(p1)
        RETURN p1.name AS name1, p2.name AS name2
        """
        result = db.query(query, {"name1": name1, "name2": name2})
        if result:
            return f"Friendship created between {name1} and {name2}"
        return "Error creating friendship"

    @strawberry.mutation
    def delete_person(self, name: str) -> str:
        """Delete a Person node"""
        query = "MATCH (p:Person {name: $name}) DETACH DELETE p"
        db.query(query, {"name": name})
        return f"Person {name} deleted"


# Set up GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

# FastAPI app
app = FastAPI()

# GraphQL router
graphql_router = GraphQLRouter(schema)
app.include_router(graphql_router, prefix="/graphql")


# Close connection on shutdown
@app.on_event("shutdown")
def shutdown():
    db.close()
