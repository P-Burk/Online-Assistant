import os
from typing import List

from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient, ReturnDocument
from bson.json_util import dumps


class DBHandler:

    def __init__(self):
        self.MONGO_USERNAME = os.getenv("MONGODB_USERNAME")
        self.MONGO_PASSWORD = os.getenv("MONGODB_PASSWORD")
        self.MONGO_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING")
        self.MONGO_CONNECTION_STRING = self.MONGO_CONNECTION_STRING.replace("<username>", self.MONGO_USERNAME)
        self.MONGO_CONNECTION_STRING = self.MONGO_CONNECTION_STRING.replace("<password>", self.MONGO_PASSWORD)
        self.MONGO_DATABASE = "Online-Assistant-DB"
        load_dotenv(find_dotenv())
        self.__connect()
        self.db = self.client[self.MONGO_DATABASE]

    def __enter__(self):
        self.__connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__disconnect()
        if exc_type:
            raise exc_type(exc_val)
        return self

    # attempts to connect to the MongoDB database
    def __connect(self):
        try:
            self.client = MongoClient(self.MONGO_CONNECTION_STRING)
        except Exception as error_msg:
            print(error_msg)
            print("Failed to connect to MongoDB instance.")

    # close the connection when done
    def __disconnect(self):
        self.client.close()

    # def __find_document(self, query: str, collection_name: str) -> None | object:
    #     """
    #     Private method to check collection for documents and return cursor object if documents are found
    #     :param query: Dict
    #     :return: None or pymongo cursor
    #     """
    #     document_count = self.db.get_collection(collection_name).count_documents({})
    #     if document_count == 0:
    #         return None
    #     return self.db.get_collection(collection_name).find({}, {"_id": 0, f"{query}": 1, "general_questions": 1})

    def read_all(self, doc_field: str, collection_name: str) -> None | object:
        """
        Returns a cursor containing documents that meet the search query criteria.
        :param collection_name: name of the collection to search.
        :param doc_field: Dictionary containing the search criteria.
        :return: None if no documents are found, otherwise a cursor object.
        """
        output = self.db.get_collection(collection_name).find({}, {"_id": 0, f"{doc_field}": 1})
        if output is None:
            return None
        output = dumps(output)
        return output

    def read_example_order(self) -> str | None:
        """
        Returns the example order document so that you can prompt chatGPT with order format.
        :return: string of the example order.
        """
        output = self.db.orders.find_one({"name": "EXAMPLE_ORDER"}, {"_id": 0})
        if output is None:
            return None
        output = dumps(output)
        print(type(output))
        return output

    def get_all_field_names(self, collection_name) -> List[str]:
        """
        Returns a list of all field names in a collection.
        This is useful for determining what fields are available and using that to have ChatGPT classify the question.
        :param collection_name: name of the collection to search.
        :return: List of all field names in the collection.
        """
        all_documents = self.db.get_collection(collection_name).find()
        field_names = set()
        for document in all_documents:
            field_names.update(document.keys())
        field_names = list(field_names)
        field_names.remove("_id")
        return field_names

    # def insert_order(self, query: dict):
    #     """
    #     Inserts a single document into the orders collection.
    #     :param query: dictionary of content to add to the database.
    #     """
    #     try:
    #         self.db.orders.insert_one(query)
    #     except Exception as error:
    #         print(error)
    #         print("Failed to add order to database.")

    # def update_orders(self, query: dict, update_data: dict, multiple_orders: bool) -> None | object:
    #     """
    #     Updates one or many orders.
    #     :param query: documents to find.
    #     :param update_data: data that will be updated to the order(s).
    #     :param multiple_orders: selector for updating a single order or multiple orders.
    #     :return: No document(s) found - None.
    #              Single update - the updated document.
    #              Multiple updates - pymongo.returnResult.
    #     """
    #     if query is None:
    #         raise Exception("No data provided for query.")
    #     if update_data is None:
    #         raise Exception("No data provided for update.")
    #
    #     update_data = {"$set": update_data}
    #
    #     # logic for updating a single order
    #     if multiple_orders is False:
    #         return self.db.orders.find_one_and_update(query, update_data, return_document=ReturnDocument.AFTER)
    #
    #     # logic for updating multiple orders
    #     result = self.db.orders.update_many(query, update_data)
    #     if result.modified_count == 0:
    #         return None
    #     return result

    # def delete_orders(self, query: dict, multiple_orders: bool) -> None | object:
    #     """
    #     Deletes one or many orders.
    #     :param query: documents to find.
    #     :param multiple_orders: selector for deleting a single order or multiple orders.
    #     :return: No document(s) found - None.
    #              Document(s) deleted - pymongo.deleteResult.
    #     """
    #     if query is None:
    #         raise Exception("No data provided for query.")
    #
    #     if multiple_orders is False:    # logic for deleting a single order
    #         result = self.db.orders.delete_one(query)
    #     else:                           # logic for deleting multiple orders
    #         result = self.db.orders.delete_many(query)
    #
    #     if result.deleted_count == 0:
    #         return None
    #     return result
